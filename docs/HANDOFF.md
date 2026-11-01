# Handoff

## Núcleo Win32 privado revisado com fakes — 2026-11-01

Claude2, único programador Opus5.5/esforço medium, implementou o backend
`pg16_shell_admission_win32.py` (`10c9058f`) e testes (`ab279a10`). O assistente
principal revisou e validou:105 próprios/1,24s, cinco cenários independentes
CLEAN/0,16s;740 relacionados/17arquivos/293,99s, sem falhas/skips. Ruff/lint restrito,
format347/mypy341 alvos311/314 limpos; runtime sóWindows3113. Primeira versão
87passed/1failed mais cinco findings reproduzidos foi rejeitada; cópia pública
dos bytes preservada no arquivo de revisão, sem execução nativa. Saídas
indeterminadas não são propriedade, interrupção de criação fica HELD e quadro
de PIDs curto não permite liberação. Ver SHELL-ADMISSION-WIN32-VALIDATION.

Sem consumidor/CLI, kernel32/job/handle/processo nativo deste backend, controle
ou raiz operacional. Próximo: chamador/fakes; controle/comando/proposta próprios
antes de efeitos.3s NOT_MEASURED; Gateway/B1/B2/D090/C1/SQL/produção abertos.
Desvio de leitura pyvenv.cfg registrado sem aprovação retroativa; conteúdo não
usado como prova. Regras da CLI endurecidas e dois canários de deny conferidos,
sem alegar sandbox de SO. Nenhum escritor ativo/quota/job novo; fontes aceitas
e raízes consumidas intactas. Registros seguintes históricos.

## Sonda de admissão revisada com fakes — 2026-11-01

Claude2 implementou `pg16_shell_admission_probe.py` (SHA `738ee1e3`) e testes
(`5dd02d7b`), Opus 5.5/esforço medium; o assistente principal revisou/testou.
85 testes próprios/20,13 s, sete verificações independentes CLEAN/0,60 s e
635 relacionados em 16 arquivos/270,87 s, todos exit 0, sem falhas ou skips.
Ruff/lint restrito do helper limpos, format 345 e mypy strict 340 arquivos nos
alvos 3.11/3.14; runtime somente Windows/Python 3.11.3. Primeira rodada
77passed/7failed/2errors e seis correções do desenho preservadas na validação.
As falhas de harness foram corrigidas pelo Claude2 sem alterar o helper.

Claim exclusivo antes da medição; relógio/limite float originais, categorias
fechadas, marca e pendente verificados antes do rename final sem I/O posterior.
Parecer aprovado no componente isolado, sem P1/P2 remanescentes. Ver
SHELL-ADMISSION-DESIGN/VALIDATION. Sonda nativa, raiz operacional, executáveis/
configuração reais e Docker/PG/SQL/worker/serviço não foram acionados neste lote.
Gate 3 s continua NOT_MEASURED; próximo é procedimento nativo com registro
prévio de invocação, supervisão/coleta e comando literal revisados antes de
qualquer materialização/execução. Fontes aceitas e raízes consumidas intactas.
Sem escritor/revisor ativo, nova quota ou job; retomada antiga concluída e
desativada. Gateway indisponível; B1/B2/D090/C1/produção abertos. Histórico abaixo.

## Preparador do leitor PG16 revisado e validado — 2026-10-31

Claude2 concluiu `pg16_shell_prepare.py` (SHA `8d0bf39e`) e seus testes
(`ed027162`), sempre Opus 5.5/esforço medium. O assistente principal revisou:
43 testes próprios/33,34 s, sete verificações independentes CLEAN/22,47 s,
550 relacionados em 15 arquivos/264,07 s, sem falhas ou skips. Ruff e lint
restrito do helper limpos; format 343 arquivos, mypy strict 339 arquivos nos
alvos 3.11/3.14. Runtime somente Windows/Python 3.11.3. A falha inicial da
fixture e a imprecisão sobre os pins estão preservadas na validação; ambas
corrigidas, sem mudança no preparador para acomodar o teste.

Estado puro: 16 campos/6.959 bytes/23 casos, FRESH/invokedFalse. Proposta sem
escrita/leitura do launcher; materialização exclusiva com recusa de reuso.
Parecer aprovado no componente isolado, sem P1/P2 remanescentes. Ver
SHELL-PREPARE-VALIDATION/DESIGN/REVIEW. Admissão nativa em 3 s continua
NOT_MEASURED; a sonda ainda exige desenho/procedimento próprios, inclusive
consumo durável antes da medição. Nenhuma raiz operacional ou Docker/PG/SQL/
worker/serviço neste lote. Fontes aceitas e medição consumida `3eb3` intactas.
Retomada das 21h45 comprovada, resultado 0; tarefa única desativada depois,
sem próximo horário. Nenhum escritor/revisor ativo, quota ou job novo.
Gateway indisponível; B1/B2/D090/C1/produção abertos. Registros abaixo históricos.

## Exportador dos 23 casos revisado e validado — 2026-10-31

Claude2 é o programador único, Opus5.5/esforço medium por preferência explícita
atual do usuário; assistente principal revisa/testa. Exportadored491c01 e
testes906a8cae:54passed/110,51s, cinco contraprovas independentes CLEAN/18,21s,
481relacionados213,91s, Ruff/format341/mypy338 alvos3.11/3.14 limpos, runtime
Windows3113. QuatroP2/umP3 iniciais reproduzidos e corrigidos pelo Claude2,
13regressões acrescentadas. Parecer do revisor aprovado no componente isolado;
ver SHELL-EXPORT-VALIDATION/DESIGN. Próximo preparador/estado≤32768/admissão3s/
proposta/comando antes de rodada. Sem revisão/escritor/Claude2 ativo, quota/job
novo. Só fakes/arquivos próprios, sem Docker/PG/worker/SQL/serviço/observação
nova do Desktop.3eb3 intacta/consumida. Gateway indisponível; B1/B2/D090/C1/
produção abertos. Registros abaixo históricos.

## Diagnóstico e envelope prospectivo aceitos — 2026-10-31

Após2034cd4 publicado, task3eb3f616e3f24f3e943bd2135b0007ba executada uma vez,
exit0/MEASURED/SOURCE_UNCHANGED em7,272s. Três artefatos públicos conferidos:
result2257bytes/SHA71eb429d,20samples; evidência aceita69592. Root consumido,
NÃO editar/repetir. Envelope prospectivo aceito47012 após orientação1125 e
quatro precisões incorporadas: estimativas176,94/289,08 e cauda578,84s, não
latência demonstrada de owner/CLI/fsync. Ver PIN-CAPTURE-RUN-VALIDATION e
SHELL-BUDGET-DESIGN. Próximo exportador23diretórios/preparador/estado≤32768/
admissão3s/proposta/comando revisados antes de nova rodada. Sem Docker/PG/
worker/SQL/serviço/observação nova do Desktop, quota/job/revisão ativa/outro
escritor. Gateway/B1/B2/D090/C1/produção abertos. Históricos abaixo.

## Helper de custo dos pins aceito, sem medição real — 2026-10-31

Helper0195b1e4/12028bytes aceito99073, só código/fakes.37próprios11,61s e
399relacionados104,82s, Ruff/format339/mypy336 alvos3.11/3.14 limpos,
runtimeWindows3.11.3. Dois Hosts/final0/final23,20amostras/ordem fixa,
construtores reais sem start/raiz/loop, stdout/schema fechados. Duas regressões
bool/duas IO vermelhas antes dos fixes. Contagens distinguem observado de
PS/clock/final substituído; compile fora de pins e limites de pior caso ainda
entram no orçamento. Nenhum executável/config real lido, Docker/PG acionado,
raiz operacional ou segundo escritor. Próximo: comando único de leitura
revisado antes de executar. Sem quota/job/revisão ativa; Gateway e B1/B2/
D090/C1/SQL/produção seguem bloqueados. Registros seguintes históricos.


## Entrada pública do leitor PG16 aceita, sem execução — 2026-10-31

Entradaafaffad0/24081bytes aceita pelo Claude2 em58487, só código/fakes.
58próprios/35,14s e362relacionados/77,86s aprovados; Ruff/format336/mypy334
alvos3.11/3.14 limpos, runtimeWindows3.11.3.7256 preservado: prova terminal
tardia, duas regressões vermelhas antes do fix. Agora físico+all_tasks antes
de passed/escritas, releasedFalse em HELD, categorias da entrega exatas.
Callback externo pós-finish é risco residual da TCB documentado, sem aval
individual inventado. FontesHost8c/consumidas intactas; nenhum Docker/PG
acionado. Sem raiz/estado/comando operacional/export/prep ou outro escritor.
Orçamento de pins/proposta nativa bloqueados até medidas próprias; Gateway
indisponível, B1/B2/D090/C1/SQL/produção abertos. Sem quota/job/revisão ativa.
Este é o estado corrente; os registros seguintes são históricos.


## Coordenador público do leitor PG16 aceito, só definições — 2026-10-30

Host8c41605f/40791bytes aceito pelo Claude2 em61196, só definições/fakes.
52próprios/49,90s; Ruff/format334/mypy333 alvos3.11/3.14 limpos, runtime
Windows3.11.3. P2 das revisões29625/59784 corrigidos com regressões vermelhas:
pins puro+gate após hashes, teardown continua/coleta todos, inspect ligado
a label/índice/artefato e categorias dos19negativos preservadas. NOT_INVOKED
distinto de create ambíguo; checkpoint/journal reais, timeout e constructors
reais com start simulado. Heartbeat cancelado só é coletado na nova tentativa
quando o próprio foreground não está sendo cancelado. Fired sempre reprova.
Cada caso exige release/volumes/join/nofire. Sem main/entry/export/prep/raiz/
Docker/shell/PG novo; Timer auxiliar real. Custo dos pins fica fora dos seconds
antigos: medir/somar antes de proposta nativa; orçamento B300 não liberado.
B1/B2/D090/C1/SQL/produção abertos, Gateway indisponível, nenhum outro escritor.
Este estado substitui o estado corrente dos registros anteriores abaixo.


## Entrega pública do leitor PG16 aceita — 2026-10-30

Variante42f7e647/2528bytes aceita pelo Claude2 (42864).25testes próprios
incluídos em143relacionados/5,97s; Ruff/format333/mypy311/314332 limpos,
runtime Windows3.11.3. Só constructor difere de d671; nove HEADER levam
prefixo≤16bytes (short15),14casos preservam wire/chunks exatos. Wrapper/core/
parser/prazos e IO/BrokenPipe permanecem; metadata descreve configuração,
não syscall/recepção. GuardTimer de pytest é real, não watchdog do ensaio.
Hostdesenho2192 aceito com oito precisões incorporadas antes de código:
23monitores preparados antes de A, gates por record, artefatos/diretórios
próprios, Bstart global, todos joins, callbacks vinculados e exit0/42 real.
Host ainda não implementado; B300 é meta fail-closed, margem534<600,
não soma de piores casos. Nenhum Docker/shell/seed/raiz operacional novo.
Fontes consumidas intactas; Gateway indisponível, B1/B2/D090/C1/produção
abertos. Próximo: host com fakes, depois entry/export/prep/rodada revisados.

## Watchdog do leitor PG16 aceito, só definições — 2026-10-30

Variante cf6634da/17411bytes aceita pelo Claude2 (74378 após21812).33testes
próprios/122relacionados5,72s, Ruff/format332/mypy311/314331 limpos; runtime
sóWindows3.11.3. Oito regressões B1 vermelhas antes do Store monotônico;
nota de __eq__ também reproduzida antes de validar tipo antes da comparação.
Um Store/CID por caso; Bstart global não se renova. _bound antes de qualquer
CLI, fired sempre HELD, join não libera. 54cc/6e38 e fontes consumidas intactos.
Nenhuma thread/CLI/Docker/PG/seed/raiz novo. Get-Process observou DesktopOff
em18:05:18Z (pontual). Próximo: desenho do coordenador/caller público do leitor,
matriz/entrega exatas, exportador e entrada/proposta antes de efeitos nativos.
Gateway indisponível; B1/B2/D090/C1/SQL/produção abertos. Sem job novo ou
segundo escritor. CHECKPOINT-2026-10-30 registra a continuação e os limites.

## Posse do leitor PG16 aceita, sem efeitos — 2026-10-30

Adapter96e8a4c/3984bytes aceito pelo Claude2 (review35578).37testes próprios/
117relacionados3,74s, Ruff/format331/mypy311/314330 limpos, runtime sóWindows
3.11.3. Tipos JSON exatos bloqueiam igualdade hostil; captura vinculada a
task/case/wrapper/CID, independente de Env/aceitação. Sem reread vivo, CLI,
admissão, rm ou autoridade de release. Namespace capturado é TCB, hash não
o autentica após exec. Perfil8906/owner d671/reader efe6 intactos.
Próximo: desenho/variante de watchdog própria antes de caller ou efeitos.
Nenhum Docker/shell/PG/seed/raiz novo; DesktopOff, Gateway indisponível.
B1/B2/D090/C1/SQL/produção abertos. Sem quota/job ou segundo escritor.

## Perfil interativo PG16 aceito, sem execução nativa — 2026-10-30

Perfil8906e846/8415bytes aceito pelo Claude2 (review28829), manifesto867617ca.
55testes próprios/205relacionados3,76s, Ruff/format330/mypy311/314329 limpos;
runtime sóWindows3.11.3. Duas regressões de Mounts malformados falharam antes
do fix. Todos23casos medidos para argv Windows: máximo4747/margem21253.
Wrapper/manifest próprios, stdintrue/true/TTYfalse, Attach* só observações.
Nenhum Docker/shell/PG/seed/caller novo, nem alteração das fontes consumidas.
Bloqueio transitório do aprovador automático resolvido; revisão executada,
nenhum limite do Claude2 atribuído. Próximo: cleanup/watchdog/caller específicos
do leitor e entrega exata antes da rodada. DesktopOff, Gateway indisponível;
B1/B2/D090/C1/SQL/produção abertos. Sem quota/job ou segundo escritor.

## Canal público do leitor PG16 aceito — 2026-10-30

Owner d6718800 foi aceito pelo Claude2 após a correção L1 (review60994).
O teste de callbacks falhou antes do fix; depois passaram33 testes próprios
e168 relacionados/7,61s, com1 unidade nativa explicitamente desmarcada.
A seleção anterior167/1falha WinError5 permanece registrada; não se repetiu
a prova nativa de pipes. Ruff/format329/mypy311/314328 limpos, runtime só
Windows3.11.3. RETAIN/WAIT mantêm stdin aberto; observação leva exit e contagens
reais. Sem caller, shell, Docker, banco ou segredo novo; Desktop continua Off.
Próximo: perfil explícito do wrapper e desenho da entrega/matriz nativa antes
de efeitos. Fontes consumidas anteriores intactas. Gateway indisponível,
B1/B2/D090/C1/SQL/produção abertos; sem quota/job ou segundo escritor.

## Leitor shell PG16 aceito, somente código puro — 2026-10-30

Novo helper efe69a79 (núcleo80219269) aceito pelo Claude2 emreview32442.
B1 de NUL final corrigido no desenho antes do código;30testes próprios e
408relacionados/82,03s passaram. Ruff/format328/mypy311/314327 limpos,
runtime Windows3.11.3.23vetores públicos e parser por exit real; nenhum shell,
Docker, banco ou segredo executado. Nota para próxima composição: RETAIN
exige variante que não feche stdin; e6ca fecha e produziria EOF, não QUIET.
Rodada PG pública anterior486481f publicada e consumida, intacta, DesktopOff.
Próximo: perfil/canal/host públicos do leitor, revisão antes de efeitos.
B1/B2/D090/C1/SQL/produção abertos; Gateway indisponível. Sem job/quota ou
segundo escritor. Registros seguintes são históricos.

## Sonda pública PG16 concluída e revisada — 2026-10-30

Rodada única task81e72756/rootc3a916a7 terminou exit0/PG16_PUBLIC_VERIFIED.
Claude2 aceitou os fatos em2026-10-30T14:41:43Z, sessão51ea0d85.12 checkpoints
119515ms/34comandos0, perfil aceito em3inspects, PG16.15/Alpine3.24.1/UID70.
OwnerCLOSED/released, CID removido,17volumes→17 conjuntos iguais, watchdog
joined/nofire/heldfalse. DesktopOff observado externamente14:32:51Z.
Export95f0 único reteve50fontes77312bytes; sósummary/transport derivados
publicados. RUN-VALIDATION registra limites e duas notas do revisor: próximo
resumo deve incluir returncode/stdout_bytes do owner e rótulo do inspect final.
Fontes/root/script consumidos congelados, nenhum recurso vivo pendente.
Próximo: leitor shell exato e fixture PG privada, com revisão própria antes
de efeitos. Nenhum initdb/servidor/SQL/seed/credencial neste ensaio.
Gateway indisponível; B1/B2/D090/C1/SQL/produção abertos. Sem quota/job ou
segundo escritor. Registros seguintes são históricos.

## Preparo e exportação PG16 aceitos — 2026-10-30

Preparador02d1dadd e desenho aceitos pelo Claude2 (55166); exportador95f09bbb
por projeção aceito94684.378 testes conjuntos passaram em52,39s, Ruff/mypy311/
314326 e format328 limpos. Raw nunca é publicado: summary/transport derivados,
volumes/ledger/report/journal validados. Dois fixes de alias/marker e cinco
sobre tipos/coerência tiveram regressões vermelhas primeiro. Precisões do
último inspect e do source_unchanged antes da escrita documentadas.
Próximo: proposta exata de raiz/task/estado/script e revisão antes de qualquer
materialização/rodada. Nenhum novo Docker/PG/SQL/seed/credencial ou serviço.
Fontes/raízes consumidas intactas. DesktopOff, Gateway indisponível e gates
B1/B2/D090/C1/produção abertos. Sem quota/job ou segundo escritor.

## Registro anterior — entrada PG16 pública aceita — 2026-10-30

Incremento commitado emf51d63a. Clone novo autocrlftrue/sem hardlinks confirmou
698/698 arquivos iguais e entradaa6089275 preservada; evidência pública em
checkpoint-entry-portability-20261030. Somente cópia de bytes, sem executar app.

Checkpoint81ead94 publicado para continuidade. Entradaa6089275 implementada
sobre host7275, aceita pelo Claude2 (32225), condição319testes atendida:
319passed43,26s, Ruff/format325/mypy311/314324 limpos. B1 diagnóstico corrigido
com24 regressões vermelhas primeiro; categorias/origens por tipos capturados,
conjuntos AST só em teste. HELD conserva loop/owners; restore incerto não
inventa interrupção nem para Desktop. Sem Docker/PG/SQL/seed/credencial novo.
Próximo: exportador PG próprio que retém local-* e baseline completa, depois
preparador/proposta/raiz/comando e revisão antes de rodada única. Nenhuma raiz
ou tentativa operacional PG16 materializada. Fontes consumidas intactas.
DesktopOff, Gateway indisponível, B1/B2/D090/C1/SQL/produção abertos. Sem
quota/job ou segundo escritor. Publicação do incremento deve ser conferida
pelo Git; registros abaixo são históricos.

## Registro anterior — checkpoint para continuidade — 2026-10-30

Checkpoint7875dc8 e correção5dc1f6a commitados; clone novo autocrlftrue,
695/695 fontes/evidências iguais, pyproject917fe735/CRLF preservados. Primeira
rodada693/694 reprovada preservada. Metadados aceitos pelo Claude2 (64823).
Publicação/sincronização devem ser confirmadas pelo Git, não por este texto.

Usuário solicitou commit de todo o trabalho acumulado antes de mudar de local.
HostPG16 corrigido7275c8ae aceito10847: info/version bruto descartado, só projeção
pública persistida, stop zerado em finally.39fakes12,98s e seleção final dos
sete componentes257passed16,70s; Ruff/mypy311/314323 limpos. Sem efeito nativo
novo. `.gitattributes` preserva bytes de docs/poc/deploy, inclusive CRLF
histórico; não renormalizar fontes consumidas. CHECKPOINT-2026-10-30.md orienta
continuidade. Falhas e limitações históricas preservadas; sem release.
Próximo: entrada PG16/HELD, exportador local-only/S1, preparador/proposta e
revisões antes de rodada única. Sem entrada/root/comando operacional ainda.
Config pessoal/dumps/systeminfo fora do commit. Imagens/Temp/wheels/ambientes
não são transportados pelo Git; nova máquina exige readmissão própria.
DesktopOff, Gateway indisponível e B1/B2/D090/C1/SQL/produção abertos.
Sem quota/job ou segundo escritor. Não há revisão ativa neste instante.

## Registro anterior — PG16 público — coordenador em revisão, sem efeitos — 2026-10-29

Perfilfe2f aceito6796, ownera02f aceito70705, adapterf1d9 aceito5979,
volumes6e38 aceitos78090. Watchb868/emergency54cc aceitos17011 após minimizar
nomes e corrigir flag antes de fsync;218focados5,18s/estáticos322 limpos.
Novo hostd63650d6 integra somente definições4bc/b593 e colaboradores PG:
36fakes8,21s, cinco regressões próprias vermelhas antes do fix; Ruff/mypy311/
314323 limpos. CLI fechada, baseline30s+listagem antes de create, um create,
decisão durável antes de rm/v, conjunto final/ownerclose/join antes de stop.
Raw/baseline completos local-only, exportador futuro deve reter. Sem entrada/
root/comando operacional; host em revisão antes do próximo incremento.
Falha temporal histórica250(A249/1falha;B250) preservada na CLEANUP-VALIDATION,
causa indeterminada. Nenhum novo Docker/PG/banco/SQL/secret/worker, DesktopOff;
Gateway indisponível, B1/B2/D090/C1/produção abertos. Sem commit/push/job/
quota ou segundo escritor. Registros seguintes são históricos.

## Registro anterior — T4 v2 medida e aceita — 2026-10-29

Rodada de8e832c/task42d363a1 terminou0/ORACLE9_T4_V2_VERIFIED, sete casos/owners
liberados e sete CIDs próprios removidos.12checkpoints119281ms/66comandos0,
watchdogjoined/nofire/heldfalse, inventário vazio e DesktopOff13:15:07Z.
ExportS1aeade45d:53fontes732390bytes/53publicadas0retidas, transporte3a274347
aceito pelo Claude2 (39884). Normal/reader-negative16384iguais/EOFtrue; retain
vivo após CLIreap e removido depois. SENT só pipe local. T4antiga0566 intacta.
Fontes3a5b/28b5/aead/8e02 e raiz agora consumidas, não editar/reexecutar.
Desenho PG16 público60182/P1 confirmado22157. Núcleo puro de volumes6e3827af:
33testes0,27s/estáticos317 limpos, aceito78090, sem caller/CLI/release.
Perfil/builder/parser/S1 puros fe2f8ba8 implementados:120focados0,91s/estáticos
318311/314 limpos; fixes ulimits/Env/TAB com regressões vermelhas antes.
Em revisão6796 junto ao desenho PUBLIC-HOST-DESIGN, ainda sem owner/host/
rodada PG nova. Só memória, ferramentas/UID/tmpfs reais não medidos neste
lote. Leitor shell/segredos continuam posteriores. Nenhum novo Docker/PG/banco/SQL/worker
ou serviço operacional; Gateway indisponível. B1/B2/D090/C1/produção abertos.
Sem commit/push, quota/job ou segundo escritor; DesktopOff, nenhum recurso vivo.

## Registro anterior — T4 v2 em execução em2026-10-29

Proposta aceita pelo Claude2 (review52272); materializada uma vez,3305bytes/
bec0accd iguais à proposta, sóattempt e comando iguais. DesktopOff confirmado
13:11:00Z. Scriptb01ce0b2 invocado uma vez, sessão10282 em andamento: NÃO repetir
root/main, iniciar outro DockerCLI/escritor ou editar fontes agora consumidas.
Raizde8e832ca4c67fd35f3647779adfaad0/task42d363a1115633d15fbb809fc0dc666e.
Aguardar terminal e provas de recursos; depois exportaeade45d uma vez viaS1,
sem ler raw em ferramentas/conversa antes do filtro. HELD não exporta/reexecuta.
Canários públicos somente; sem PG/SQL/serviço. Gateway indisponível e gates
B1/B2/D090/C1/produção continuam abertos. Sem quota/job/segundo escritor.

## Registro anterior — T4 v2 preparada e revisada em2026-10-29

Perfil3a5bb9a3/main28b56013 aceitos pelo Claude2 após corrigir C1 herdado;
65 testes novos aprovados em14,41s, quatro overrides/driver preservados.
Exportaeade45d/prep8e024cf4 aceitos;28testes31,07s, retain vivo passa S1 próprio
com SHA/tamanho ligados à CLI. Ruff/mypy311/314 em316arquivos limpos, runtime
sóWindows3113. Proposta checkout oracle9-t4-v2-prep-20261029, RootTempde8e832c/
task42d363a1/estado3305bytesbec0accd/scriptb01ce0b2 em revisão antes de qualquer
materialização ou invocação. Nenhum novo DockerCLI/PG/container/attach/seed;
DesktopOff confirmado13:09:54Z. Fontes/raízes consumidas anteriores intactas.
Sem quota/job/outroescritor, T4/B1/B2/D090/C1/SQL/produção abertos; indisponível.

## Registro anterior — admissão medida em2026-10-28

Rodada2dd94bfb/task34346ce8 terminou0/ORACLE9_ADMISSION_CAPTURED, sócreate/
inspect de dois perfis, nuncastart/attach/owner/seed. Única divergência nos
dois: StdinOncefalse esperado/true observado, CONFIG/profileacceptedfalse;
demais predicados iguais, labelsCID3/imagem4.12checkpoints119156ms,33comandos0,
doisCIDs removidos/ausências/inventário vazio/threadjoined/DesktopOff; relido
Off19:18:42Z. Exportador S1recalculado:33fontes204300bytes/33publicados/0retidos,
transporte4f771777 aceito pelo Claude2 como diagnóstico, sem liberar perfil/
canal. Fontes96/7c/1b/beeb e raiz agora consumidas, congeladas, além das T4antigas.
Novo desenho T4v2 em review27358: só predicadoStdinOnceTrue, outrosperfistetos/
fábrica/leitor/canário iguais, rawantesvalidação/S1 todosaliases inclusive
retainvivo. Sem código/root/Docker novo nesse desenho, sem quota/job/segundo
escritor. T4/B-1/B-2/D-090/C1/SQL/PG/produção abertos, Gateway indisponível.

## Registro anterior — execução de admissão em andamento

Proposta2dd94bfb/task34346ce8, código e comando aceitos pelo Claude2.
Materializados2392bytes/SHA24d647a0 iguais à proposta/onlyattempt/comando;
scripta17e4275 invocado uma vez19:14:58Z, Desktop inicialmente Off. Sessão91808
em andamento: NÃO iniciar outra CLI/Docker/escritor ou repetir root/main.
Aguardar terminal e provas de recursos antes de exportador S1beeb85d6;
nenhum raw em ferramenta/conversa/repositório antes desse filtro. Sem start
de container/attach/seed/PG/SQL. Fontes T4consumidas preservadas, Gateway
indisponível e gates de produção ainda abertos.

## Registro anterior — proposta exata de admissão

Comparador9612/71, runner7c113617/20, exportadorbeeb85d6/16 e preparador1b069987/8
aceitos pelo Claude2.115focados16,07s, Ruff/mypy311arquivos311/314 limpos,
runtime só3113. Variante só cria/inspeciona normal e retain, nunca inicia
container/attach/owner/seed; todos aliases raw passam S1 antes de exportar.
PropostaRoot2dd94bfb4502755ce8fa8cd496f637c8/task34346ce8ed18f936d482c3c19aaeb04f,
estado2392bytes/SHA24d647a0/scripta17e4275 em revisão antes de materializar;
root ainda não existe, sem DockerCLI novo. T4reprovada0566/raiz86e5 e fontes
88e2/835c/c789 intactas, DesktopOff. Sem quota/job/segundo escritor. T4/B-1/
B-2/D-090/C1/SQL/PG/produção abertos, Gateway indisponível.

## Registro anterior — T4 reprovada na admissão, recursos restaurados

Rodada única86e5417c/task52cdd340 terminou exit1/NOT_PASSED, antes de owner/
attach/start/seed.12checkpoints/replay121360ms, createCID94d9d33a confirmado,
inspect31711bytes validou posse mas não aceitação. Raw não persistido antes
da validação: lacuna explícita, sem atribuir campo/causa.28comandos0, rm próprio/
ausência/inventário vazio, threadjoined e DesktopOff comprovados. Transporte
24arquivos37910bytes/SHA0566dd40, resultado aceito pelo Claude2 como baseline
reprovada. Não repetir fonte/raiz consumidos88e2/835c/c789. Nenhum recurso vivo
pendente. Próximo desenho create/inspect público somente, captura antes da
validação e categorias fechadas, sem start/attach/seed/PG; ainda sem código ou
efeito novo. Núcleo puro de diferenças/publicação72e8/66 aceito; reforço9612/
71tests em rerevisão (4regressões vermelhas antes). Vincula CID/nome capturados,
varre proxy/auth e oculta texto/Env. Nenhum chamador/exportador operacional;
Ruff/mypy308311/314 limpos, runtime só3113. Desenho S1/fivehooks para integração,
sem nova raiz/rodada. B-1/B-2/D-090/C1/SQL/produção abertos, Gateway indisponível.

## Registro anterior — execução T4 em andamento

RootTemp86e5417cd7958015ace880173d138553/task52cdd3407a6bcc71f77d8d2610c59e5c
materializados uma vez, bytes2254/SHA26548003 iguais à proposta aceita;
script6ddb78bf invocado uma vez17:53:03Z, Desktop inicialmente Off. Primeiras
2observações/3checkpoints xb conferidos, sessão50033 em andamento. Não iniciar
outra CLI/Docker/escritor, não repetir main/raiz. Aguardar término e capturar
evidência integral antes de qualquer próximo lote. Host88e2/entry835c/prepc789
originais aceitos, labelimagem4/CID3 conforme inspect real. Proposta anterior
de herança1f rejeitada, nunca materializada; preservada. T4 pública sem PG/
seed privado/SQL; C1/B-1/B-2/D-090/produção continuam abertos, Gateway indisponível.

## Registro anterior — preparo do código T4

Canale6ca/77, canárioe3cf/47, identidadedc248/28fakes, emergência2fdc/22 e
watchdog3e98/26 revistos pelo Claude2. Prova nativa única de identidade:
1pass/1,45s, somente filho Python próprio+2PS, todos recolhidos; não repetir.
Seleção relacionada medida665pass/46,79s, separada das
unidades de identidade/emergência/watchdog. Binding88e220eb/32fakes aceito
após3regressões vermelhas de oráculos. Entry2e9fc/26 aceito; delta835c/27
marca interrupção no join. Preparadorc789/9 e delta em revisão, sem raiz/
estado/comando operacional. Seleção dos três novos arquivos:68pass/15,78s.
Ruff/mypy src/tests307 limpos, alvos311/314, runtime sóWindows3.11.3.
Nenhum DockerCLI/PG/seed privado novo; Desktop último estado Off, imagem621
inalterada, T4 ainda não executada. B-1/B-2/D-090/C1/SQL/produção abertos;
Gateway indisponível. Sem commit/push/job/quota/segundo escritor.

## Registro anterior — bootstrap privado aceito em 2026-10-28

Canal docs/poc/w1_bootstrap_channel.pye6ca9e60 revisto pelo Claude2;77focados
verdes e618relacionados/47,94s. R1 spawn tardio, B1 pipes e B2 cancelamento
corrigidos com regressões antes do fix; L1 callbacks também revisto. Ticket
só após CLI/tarefas/handles recolhidos; release só com ausência de CID posterior
ligada ao ticket. Entrega NOT_SENT/SENTlocal/UNKNOWN; IO não vira sucesso.
Unidade de2PipeHandles nativos passou fora do sandbox, stdlib3.11.3/Proactor
pinado; Ruff/mypy src/tests300 limpos (alvos3.11/3.14, runtime só3.11.3).
Nenhum DockerCLI/DB/credencial novo; candidata621cc7f7 inalterada. Histórico
de falhas de harness e revisões em BOOTSTRAP-CHANNEL-VALIDATION. Direção da
sonda pública T4 aceita, contratos watchdog/oráculos em revisão antes de
código próprio/estado/comando/ciclo novo. T4 ainda não executada; nenhum
seed privado autorizado antes dela. B-1/B-2/D-090/C1/SQL/produção abertos,
Gateway indisponível. Sem commit/push/job/quota/segundo escritor.

## Registro anterior — W1 instalado e sondado, evidência aceita em2026-10-28

Rodada independente v2b59388f5 em27/10:exit0/ORACLE9_W1_CANDIDATE_VERIFIED.
Imagem local621cc7f702ec34d7014809411fda7fc89ab6b95f6dc7d16315274d4a7006ef0b,
Oracle9.8/Python3.11.13, wheel6b63f239,39versões/3337paths/5módulos W1.
Update offline8,75s/probeUID10001RO/networknone4,641s;5adds/3changes,
L3real155linhas, Config4layers/labels exatos.12checkpoints124656ms replayados
no host;50comandos0(35DockerCLI), doisCIDs removidos/globalvazio/DesktopOff.
Transportee257a536:36arquivos2236940bytes; atestaçãof0c3cd54. Claude2 aceitou
como insumo fixo para próximo desenho W1/PG16, não para operação. Fontes,
tentativa1falha/recuperação preservadas. Nenhuma query/worker/DB/listener,
commit/push/deploy, quota/job ou segundo escritor. B-1/B-2/D-090/C1/SQL e
produção abertos; patches/minimalização de runtime seguem pendentes.
Gateway ainda indisponível. Próximo: prova privada com PG16 descartável,
isolamento e segredos próprios, plano/código/comando revisados antes de carga.

## Registro anterior — rodada W1 abortada e recursos restaurados, 2026-10-27

Main4bc0b083 executado uma vez, exit1 após create e antes de cp/start/pip.
CID72891af0 não iniciado/Statecreated/Pid0 ficou pendente após a tentativa.
Identidade/perfil originais válidos, somente label de apresentação
Desktop não herdado; cleanup reutilizava essa exigência adicional e recusou.
Evidência RUN-VALIDATION/transportce09d005 preserva falha; não repetir rodada.
Restore9d4fa8b9/14fakes, estado e comando revisados, execução única exit0:
CID removido/ausente, inventário vazio, DesktopOff confirmado. Transporte
c1351f16 preserva6arquivos/56089bytes, tentativa falha original intacta.
Recuperação aceita como baseline; desenho R1–R5/hooks aceito antes do código.
Novo coordenador privado v2a46227c9 em revisão somente leitura:31novos/
384relacionados aprovados,1skip symlink; Ruff/mypy src/tests299 limpos.
Cinco overrides, journal12xb/replay, posse distinta de aceitação e label
de imagem explícito. Nenhuma raiz/main/DockerCLI/CIM novo; DesktopOff.
Nenhuma instalação W1, SQL/DB/worker ou serviço operacional. Não iniciar
outro DockerCLI/escritor; permissões/gates B-1/B-2/D-090/C1 preservados.

## Preparo histórico W1 — 2026-10-27, somente preparo público

Wheel6b63f239 e contexto d4d4b29b materializados uma vez e revisados;
payload de update566c46a8 revisado, ainda sem instalação. Builders do host
7540b7bf aceitos com exigência de Config exato antes de B. Coordenador
oracle9_w1_run.py761915e2 aceito após corrigir B1/B2; delta N1 final4bc0b083
com48 testes focados verdes,338 relacionados/1skip medidos no delta anterior.
Ruff/mypy3.11/3.14 em297 arquivos limpos. Root5cb698ce/estado d43f3b2a
preparados, não invocados; revisão N1/estado/comando único em andamento.
Só fakes/arquivos públicos no Windows3.11.3, nenhum DockerCLI/clock real novo,
Desktop continua Off. Próximo: fechar revisão N1 e do estado/comando
de rodada única antes de A. Imagem87871290 ainda não inclui W1; serviço
indisponível. B-1/B-2/D-090/C1/SQL/produção abertos. Sem commit/push/job ou
outro escritor. Os registros seguintes são históricos.

## W1 privado revisado - 2026-10-26

D-121: codec v2, S1, loop e owner privados revisados pelo Claude2, sem
chamador operacional.48 testes owner/57 filho/101 codec/59 S1; selecao final
1266passed, Ruff/format/mypy3.11/3.14 em291arquivos limpos (runtime so3.11.3).
O1 de lock e fechamento incerto corrigidos com regressoes vermelhas antes
do fix. Rodada temporal reprovada do encoder preservada; repeticao final
verde sem aumentar40s, causa indeterminada. Evidencias WORKER-*-VALIDATION.
Nenhum novo DockerCLI/DB/subprocesso real/artefato instalado; DesktopOff.
Core de idade61/sampler18fakes e serieF2 unica7exit0 aceitos, boot exato
na janela169547ms. WheelW1 6b63f239 (448821bytes) em dois builds identicos,
aceito como insumo fixo; ainda sem instalacao. Proximo: desenho concreto
app-only update e integracao do ciclo fresco antes de Docker.
Imagem87871290 nao inclui W1. B-1/B-2/D-090/C1/SQL/producao abertos.
Sem commit/push/deploy, quota/job ou segundo escritor. Registros seguintes
sao historicos; permissao autonoma vigente preservada.

## Guard Linux medido — 2026-10-26

D-120: bootstrap sem chamador operacional, 106 testes novos/695 relacionados
verdes e rodada secretless na candidata87871290 revisada. Cinco diferenciais
de acesso mesmo UID; parentdeath SIGKILL/reap, PPID errado e zero descendentes.
13CLI0+2restore0, CID removido, DesktopOff17:21:32Z. Guard copiado, não wheel
novo. Desvio de pausa entre observações declarado; próximo ciclo bloqueia
idade máxima monotônica/aborta sem B. PROCESS-GUARD-VALIDATION registra fatos
e limites. Próximo: desenho de protocolo/worker privado; B-1/B-2/D-090/SQL/
produção abertos. Nenhum commit/push/deploy, quota ou job novo neste incremento.

## Registro anterior — candidata Oracle instalada — 2026-10-26

Imagem local sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a,
Oracle Linux9.8/Python3.11.13,37wheels fechados+2ferramentas vendor. Instalação
sem rede e sondaUID10001/read-only/networknone passaram:39versões/pipcheck,
1382arquivos de origem/records e cincoassets.31CLI0+2restore0, dois CIDs
próprios removidos, DesktopOff em2026-10-26T14:04:01.0239836Z. Revisão final
aceitou como base de integração, não serviço/SQL/release. Evidência:
`docs/PHASE-9-ORACLE9-OFFLINE-INSTALL-VALIDATION.md` e seus artefatos hashados.

Permanecem abertos B-1 fim a fim/B-2/D-090 gate2, worker/IPC/proteções D-119,
serviço foreground e aceitação IDE/MCP/Admin. Antes de release: examinar
patches das libs empacotadas (psycopg OpenSSL3.5.4; sistema3.5.8; crypto4.0.2)
e fechar a decisão sobre pip/setuptools/.pth do runtime final. Nenhuma
conexão a banco existente, secret ou porta de Gateway. Não repetir preparo
nem iniciar outro escritor. Registros seguintes são históricos.

## Runtime Oracle Linux medido — 2026-10-25

A imagem intermediária local com Oracle Linux 9.8 e Python 3.11.13 passou
na atestação e na sonda final (UID 10001, read-only, network none,
cap-drop ALL, 128 MiB). ID:
`sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4`.
Os nove RPMs vieram da mesma cópia verificada; sem novo download. Fontes,
manifesto e imagem identificados por hash, sem promessa de rebuild bit a bit.
154 testes direcionados passaram; 24 comandos Docker da rodada final com
exit 0. Dois containers próprios removidos, inventário vazio; Desktop
restaurado off em 2026-10-25T23:07:58.6258954Z. Nove tentativas anteriores
NOT_PASSED e imagem anterior em quarentena preservadas. Evidência:
`docs/PHASE-9-ORACLE9-PYTHON-VALIDATION.md` e cópias attempt10/summary.
Revisão final 79449 aceitou esta imagem como base da preparação seguinte.
Resolução nativa posterior selecionou36wheels, sem instalação; evidência
em PHASE-9-ORACLE9-DEPENDENCIES-VALIDATION. B-1/B-2/D-090 seguem abertos.

**Gateway ainda não disponível:** faltam fechamento das dependências Linux,
aplicação instalada e integração do worker/domínio. B-1 fim a fim, B-2,
D-090 gate 2, SQL PGWire e produção continuam abertos/recusados. O destino
é Docker nesta máquina, Oracle 9.8 aceita pelo usuário; não perguntar de
novo. Userland Oracle sobre kernel WSL2, sem certificação de kernel RHEL/
Oracle ou SELinux. D-119/opção A mantém o contrato prospectivo, sem marcar
C1 pronto. Não usar o banco ou credenciais antigos de aceitação.

**Registro histórico do destino em2026-10-23 — Docker local, família Enterprise Linux9:**
O usuário indicou esta máquina, imagem RHEL9.9 ou Oracle Linux9.9, e pediu
aviso quando disponível. Ainda não existe instância pronta para testar.
Usuário aceitou Oracle Linux9 disponível9.8. Tags minor não publicadas no
DockerHub;9-slim foi conferida por digest: /etc/os-release confirmou9.8.
Primeiro attempt NOT_PASSED preservado; diagnóstico novo passou uma vez,
container próprio removido, Desktop restaurado off. Evidência em
PHASE-9-ORACLE9-BASE-VALIDATION. Python3.11 ainda ausente na base.
Userland EL9 não certifica kernel RHEL: kernel medido WSL2 nesta máquina. Contrato/
sequência em PHASE-9-CONTAINER-TARGET-PLAN. Opção A aprovada explicitamente pelo usuário: D-119, contrato prospectivo
Docker local com excesso transitório/possível queda e restart manual.
Aceite B-2 muda só para este perfil; evidência/controles ainda pendentes.
CONTAINER-MEMORY-DECISION preserva garantias e riscos explícitos. C1 NOT_READY,
B-1/B-2/D-090 e SQL/produção continuam bloqueados.
Não voltar a pedir host como desconhecido; manter históricos anteriores.

**Estado local 2026-10-23 — corpo privado do job revisado:**
D-118, runtime/worker_job.py novo, compõe uma chamada typed e um encoder;
nenhum produto anterior ou ingresso operacional alterado. SQL64KiB UTF8,
max_rows da geração, saúde/deadline por fase e somente frame completo ou
categoria fechada. J6: interrupções são fatal, dono futuro deve parar/reap;
sem lifecycle/ledger/worker novo. J7 (igualdade de metaclass) reproduzida
vermelha e corrigida para identidade is.104 próprios/1.410 relacionados
finais verdes. Rodada Unicode anterior estourou40s; causa indeterminada,
isolado30,25s e repetição relacionada107,11s passaram sem ampliar teto.
Ruff/format/mypy3.11/3.14 em267 arquivos limpos, runtime só Windows3.11.3.
Pacotes A históricos antesJ7 e B finais separados;44 módulos iguais aos
fontes, sonda só adapter fechado, não job saudável/PG/OS. WORKER-JOB-VALIDATION
e J7 revistos pelo Claude2 sem bloqueador. Dois guards admitem só este
consumidor privado; guarda operacional continua ativa. Sem novo PG/DockerCLI,
worker processual, SQL, commit/push/deploy. B-1/B-2/D-090 e produção abertos,
C1 NOT_READY; destino ainda não identificado.

**Lote anterior 2026-10-23 — erros tipados e saúde revisados:**
D-117 implementada sob delegação, sem worker/SQL operacional. Classificador
privado só typed=True; legado preservado. Continuidade exige categoria
permitida e saúde libpq positiva pós-settle, não prova de rede/read-only.
100 testes novos; PG16.15 próprio:7.503 passed/20 skips de plataforma,
nenhuma falha/erro ou skip por DSN;17 obrigatórios passaram. Container/volume
removidos, Desktop restaurado off. Wheel/sdist:40 módulos iguais aos fontes,
contraprovas stale/checkout recusadas; sonda limitada. Ruff/format/mypy3.11/
3.14 em265 arquivos limpos; runtime só Windows3.11.3. Código, procedimento
e evidência WORKER-ERRORS-VALIDATION revistos pelo Claude2 sem bloqueador.
Domínios C1 continuam NOT_READY; B-1/B-2/D-090, SQL e produção seguem
abertos/recusadas. Destino ainda não informado; sem commit/push/deploy.
Próximo: domínio real/worker e integração sob gates próprios.

**Lote anterior 2026-10-23 — C1 implementado e revisado:**
D-116, reconciliação pura em runtime/domain.py, sem chamador operacional.
Registro fechado de perfis, custos IN/OUT, grandeza única e W>=cota; ambos
perfis atuais NOT_READY, sem atestado de SO ou custo físico. Três regressões
próprias e F1 (gap Windows) corrigidas antes do aceite do Claude2; P1 da
sonda corrigido antes do uso.113 novos/916 relacionados verdes, Ruff/format/
mypy3.11/3.14 em261 arquivos; runtime só Windows3.11.3. Wheel/sdist:39
módulos iguais aos fontes, stale/checkout recusados; sonda limitada.
Evidência DOMAIN-VALIDATION e cópia de pacote revisadas sem bloqueador.
Próximo: domínio real incluindo pai/auxiliares e worker, com prova própria.
Destino ainda não informado; não presumir OS/servidor/credencial.
B-1/B-2/D-090/SQL/produção seguem abertos; sem commit/push/deploy.

**Lote anterior 2026-10-23 — HELD III real revisado:**
Procedimento corrigido por S1/R1 e revisado antes de start/A/B/C únicos.
Externo READY/exit0; control_ok/imposed/imposed,37,141s/exit0,467 linhas
iguais e14 fontes intactas. Transportes/envelopes imutáveis persistem HELD;
rechecagem lógica conserva categoria/blocos como relatos do membro, só
pico/limites corroborados. Cleanup próprio e Desktop restaurado off.
Evidência HELD-RUN-VALIDATION e cópia linux-held-20261023.json revisadas
pelo Claude2 sem bloqueador para registro diagnóstico; plano consumido.
Nenhum código de produto/teste/helper mudou neste lote. Próximo C1:
DOMAIN-DESIGN revisado, D1/D2 e R1/R2 corrigidos no contrato antes de código;
reconciliação pura com D-112, sem backend/ativação. Implementação ainda ausente.
Destino de produção perguntado ao usuário, ainda não identificado.
B-1/B-2/D-090/SQL/produção seguem abertos; sem commit/push/deploy.

**Lote anterior 2026-10-22 — integração HELD I/II revisada, só fakes:**
novos tap stdlib/wrapper PID1 e observador próprio. I1 corrigido antes de
código: captura no container, E/replay só no host, sem packaging sob -S.
Artefatos transporte/envelope separados, imutáveis, com admissão/cleanup e
pins cruzados. Prazo final corrigido após regressão vermelha de121s.
Revisões e rerevisão sem bloqueador no escopo isolado.92 testes novos
(46 I+46 II),895 relacionados verdes; Ruff/format/mypy3.11/3.14 limpos,
runtime só Windows3.11.3. Nenhum DockerCLI, factory Linux ou carga neste lote.
Evidências HELD-ENTRY-VALIDATION e HELD-HOST-VALIDATION em docs/.
Fontes/medições anteriores preservadas. Próximo gate III: procedimento,
Desktop/contexto,14 hashes e comando/rodada única revisados antes de executar.
B-1/B-2/D-090/SQL/produção continuam abertos. Sem commit/push/deploy.

**Lote anterior — evidência HELD isolada revisada:**
novo docs/poc/loaded_memory_evidence.py,59 testes novos/803 relacionados
verdes com fakes; Ruff/format e mypy3.11/3.14 limpos (runtime só3.11.3).
Envelope versionado preserva bytes exatos/hash/tamanho do original e linhas
HELD; replay lógico revalida regras/observações sem inventar tempo ou origem.
T1 reproduzido primeiro e corrigido: erro delegado mantém categoria, só
falha própria da captura gera broken/fallback. Rerevisão sem bloqueador.
Evidência: `docs/PHASE-9-STAGE-8-HELD-EVIDENCE-VALIDATION.md`.
Sem integração/entrypoint/host real, DockerCLI ou nova carga; dez helpers e
artefatos anteriores preservados. Q1 da rodada anterior não é reescrita.
Próximo: desenho/revisão da integração e perfis/hashes/comando antes de carga.
B-1/B-2/D-090/SQL/produção seguem abertos. Sem commit/push/deploy.

**Rodada anterior — loaded-as128 real revisada:**
procedimento/comandos revisados antes de uma única execução. Preflight
externo READY/exit0 conferido; interno obrigatório passou antes de create.
Controle control_ok e privado/shared128 imposed; três inventários iguais467
linhas,25,671s/exit0, cleanup e integridade confirmados. Desktop já ativo foi
preservado; sem SQL/banco/produção. Evidência e limitação da linha HELD não
persistida em `docs/PHASE-9-STAGE-8-LINUX-LOADED-RUN-VALIDATION.md`.
Revisão sem bloqueador para registro diagnóstico, com Q1–Q3: classificação
depende do supervisor hashado; escopo/kernel/imports limitados; fd/readlink
só comprovados neste perfil. Próximo desenho deve persistir HELD validado.
Não fecha contenção total/B-2/D-090 ou B-1 fim a fim. Nenhum produto/src,
dependência ou configuração mudou.
Sem retry, outro escritor, commit/push/deploy ou tarefa nova.

**Lote anterior — observador externo do laboratório (somente fakes):** novo
docs/poc/run_linux_loaded.py implementado e revisado pelo Claude2 sem
bloqueador após corrigir B1 (evidência dos negativos fortes).
75 novos testes/744 relacionados verdes; Ruff/format e mypy3.11/3.14 limpos.
Só CLI/watchdog simulados e arquivos pequenos Windows3.11.3; nenhum DockerCLI,
processo de laboratório, preparação real ou carga executado. Supervisor59/669,
produtor/coletor136/610, núcleo puro179/474 e seis rodadas preservados.
Evidência: `docs/PHASE-9-STAGE-8-LINUX-LOADED-HOST-VALIDATION.md`.
Próximos gates: procedimento externo/estado do Desktop, preflight externo
com exits conferidos, abort sem retry, comando exato e rodada única revisados.
Sem mudança de src/produto/MCP legado, dependência, ambiente, commit/push;
B-1/B-2/D-090 gate2, SQL e produção continuam abertos.

**Medição anterior preservada — sexta rodada:**
identificada --run concluída depois de revisão de código/testes/plano.
Preflight externo READY/exit0 conferido antes do observador e interno
obrigatório READY, ps/imagem aprovados. Controle normal:465 linhas
auditadas, três imports completos, native_check/binary psycopg; _openssl.lib
associado só por identidade ao slot da âncora. Wrappers algorithms/modes
vieram de seus .py pelas regras antigas, sem nova exceção. Limited AS32
falhou IMPORT/etapa0/member73: **did_not_fit**, sem atribuir causa ao AS.
complete=true significa dois casos, não contenção/fit. Sem repetição,
aumento de cota, SQL ou serviço operacional. Evidência revisada sem bloqueador:
`docs/PHASE-9-STAGE-8-LINUX-IMPORTS-LIB-RUN-VALIDATION.md`.
295 testes puros relacionados e estáticos limpos; contexto null só no
nome exato, L1(a) sem promessa global read-free. Os cinco lotes anteriores
e suas fontes preservados; desvio de procedimento da quinta continua
**não aprovado**, sem repetição retroativa. Cleanup próprio confirmado,
inventário Docker vazio antes de stop; Desktop restaurado off.
Produto/src e MCP legado inalterados neste incremento. Sem cota observada,
job novo, segundo escritor, commit ou push. B-1/B-2/D-090/SQL PGWire/produção abertos.

**Documento de entrada. Comece por aqui.**

**Delegação vigente (2026-10-20):** o usuário autorizou seguir autonomamente
até a entrega em produção, sem novo aval por lote, com revisão pelo Claude2.
Isso substitui restrições de autorização futura nos parágrafos históricos
abaixo, não seus resultados nem os gates de segurança. B-1 fim a fim, B-2 e
D-090 gate 2 continuam abertos; SQL PGWire permanece recusada. Próximos passos,
retomada conservadora de revisão e limites de deploy em
`PRODUCTION-EXECUTION.md`. O destino de produção ainda precisa ser identificado.

**Diagnóstico vigente (2026-10-20):** B2-B2a, cinco casos completos no Windows
3.11.3, após revisão do Claude2. Quatro membros mantiveram seções de 40 MiB
sob cota privada de 32 MiB; lacuna observada, não contenção aprovada. Cleanup
confirmado; sem worker/SQL, B-2/D-090 abertos. Matriz maior adiada; próximo
passo é definir cobertura compartilhada e representação limitada no pai.
Evidência revisada pelo Claude2: `PHASE-9-STAGE-8-B2-B2A-VALIDATION.md`.

**Núcleo seguinte (2026-10-20):** D-113, `pgwire/result_frame.py`, frame
imutável completo validado antes de chunks, sem materializar linhas no pai.
293 testes novos e 916 relacionados aprovados; revisão técnica pelo Claude2
sem bloqueador isolado. Sonda pura dos pacotes fora do checkout conferida,
não aplicação completa. Sem chamador operacional/SQL; receiver/2F e worker,
memória real/SSL, B-1/B-2/D-090 seguem abertos. Evidência:
`PHASE-9-STAGE-8-RESULT-VALIDATION.md`.

**Incremento posterior D-114 (2026-10-20):** receptor real limitado,
ownership e pin no ledger da sessão, sem chamador operacional. 85 focados,
1.036 relacionados e 306 antigos selecionados aprovados, com revisão
somente leitura do Claude2; Ruff/format/mypy alvos 3.11/3.14 em 238 arquivos.
Windows/CPython 3.11.3 apenas; pacotes com sonda limitada, não app completa.
Receptor já existe isoladamente, não é worker ou SQL. Contratos obrigatórios:
quarentena permanente em incerteza, erro pós-envio como saída não comprovada,
um frame por job/canal quieto. Evidência:
`PHASE-9-STAGE-8-RECEIVER-VALIDATION.md`. B-1/B-2/D-090 seguem abertos.

**D-115 posterior (2026-10-20):** API tipada opt-in no mesmo pipeline do
adapter e encoder puro de resultado já protegido, com OIDs anunciados,
preflight/alocação exata/autovalidação D-113. 408 relacionados e sondas
limitadas PG16 em wheel/sdist instalados aprovados; Ruff/format/mypy 3.11/3.14
em 243 arquivos. Revisão somente leitura do Claude2 sem bloqueador isolado.
Suíte integral PG16: **6.395 passed/20 skips de plataforma**, zero falhas/erros
ou skip por DSN; integração tipada 12/12. Só Windows 3.11.3 executado, sem worker,
chamador operacional, SQL ou produção. Evidência/contratos de fatalidade:
`PHASE-9-STAGE-8-ENCODER-VALIDATION.md`; B-1/B-2/D-090 continuam abertos.

**Diagnóstico AS posterior (2026-10-20):** quatro casos sintéticos Linux/WSL2
no Python mínimo 3.11.17, uma rodada após revisão do harness/correções:
baseline/controle positivos e recusa privada/MAP_SHARED sob AS32 MiB.
46 testes puros, estáticos em 245 arquivos; cleanup/inventário confirmados,
Desktop restaurado desligado. Evidência e hashes em
`PHASE-9-STAGE-8-LINUX-AS-VALIDATION.md`. Não mediu worker/imports reais nem
imposição dos 192 MiB externos; B-1/B-2/D-090 e SQL continuam bloqueados.
Sem produto, dependências, commit/push ou mudança de plataforma certificada.

**Atualização vigente (2026-10-19):** desenho da Etapa 8 aprovado em
2026-10-18; autorizado somente o lote B-1 de snapshot/equivalência do masking,
localmente, com revisão pelo Claude2, sem commit/push. O núcleo está
implementado, estritamente opt-in interno, sem ativação em nenhum chamador
operacional (D-111). O usuário aprovou explicitamente o lote e a D-111 em
2026-10-19, sem autorizar os próximos lotes ou commit/push. Evidência:
`PHASE-9-STAGE-8-B1-VALIDATION.md`. B-1 fim a fim, B-2 e D-090 gate 2
permanecem abertos; PGWire continua recusando SQL com `0A000`. Nenhum worker,
transporte ou mudança de cursor foi implementado. O resumo abaixo conserva
o histórico das entregas anteriores e não amplia essa autorização.

**Incremento de 2026-10-19:** autorizada e implementada somente a prova B-1
em outro processo, local e com revisão pelo Claude2, sem commit/push.
Há dois arquivos novos de testes, nenhum código de produto novo ou SQL.
O incremento foi aprovado explicitamente pelo usuário em 2026-10-19,
sem ampliar a autorização nem autorizar commit/push.
Ver `PHASE-9-STAGE-8-B1-PROCESS-VALIDATION.md`; B-1 fim a fim, B-2 e
D-090 gate 2 permanecem abertos, sem worker ou integração operacional.

**Preparação B-2 (2026-10-19):** o usuário autorizou preparar com o Claude2
o próximo lote de memória, ainda sem worker ou SQL. A proposta está em
`PHASE-9-STAGE-8-B2-PLAN.md`. Depois autorizou só **B2-A**, §4: criar o
harness temporário fora do checkout e executar após revisão do Claude2.
Sem produto, banco/Docker, worker integrado, SQL ou commit/push.
Demais lotes não autorizados e B-2 segue aberto.
Execução B2-A: seis controles e 36 casos no Windows 3.11.3, limpeza confirmada;
os 12 job-only excederam o pico configurado. Evidência revisada tecnicamente,
com o registro aprovado pelo usuário em 2026-10-19:
`PHASE-9-STAGE-8-B2-A-VALIDATION.md`. A aprovação do registro não fecha B-2
nem autoriza outros lotes, commit/push ou produção.

**Preparação B2-B (2026-10-19):** autorização posterior só para preparar e
revisar com o Claude2 o plano de contenção e orçamento global, sem implementar
ou executar testes. `PHASE-9-STAGE-8-B2-B-PLAN.md` é proposta não aprovada;
recomenda núcleo lógico isolado antes de qualquer integração. Sem pressão,
harness novo, worker, SQL, commit/push ou produção. B-2 e D-090 seguem abertos.

**B2-B1 autorizado depois (2026-10-19):** só núcleo lógico isolado de reservas
e testes determinísticos, com revisão pelo Claude2. `runtime/budget.py` está
implementado localmente, sem chamador operacional e sem mudança em registry,
lease, driver ou bootstrap. D-112 e
`PHASE-9-STAGE-8-B2-B1-VALIDATION.md`, com revisão técnica concluída sem
bloqueador no núcleo isolado; fechamento e D-112 aprovados pelo usuário
em 2026-10-20, sem ampliar a autorização.
Sem worker, SQL, pressão, integração, commit/push ou produção. Os créditos
são lógicos; B-1 fim a fim, B-2 e D-090 gate 2 permanecem abertos.

Estado: **Fase 8 concluída e publicada; Fase 9 —
Etapas 3 e 4 publicadas em `c37be36`; Etapa 5 (UX v2 somente leitura, com o refinamento
visual D-101/D-102 aprovado) publicada em `4d5b78f`; Etapa 6 (CRUD visual de
datasources e policies) autorizada em 2026-09-28, implementada localmente e
aprovada pelo usuário em 2026-09-30 (D-103–D-106, capturas e fechamento), com a
correção por Esc, e publicada em `5115a75`; Etapa 7 parcial — infraestrutura do
verificador (D-107) commitada em `e9eb01a`, e executor/barreira/leitura selada
(D-108) validado, com fechamento aprovado e publicação autorizada em 2026-10-07
(estado de publicação confirmado pelo Git); listener PGWire, TLS e
autenticação, e as Etapas 8–12, sem autorização**.
MVP e Fase 7 concluídos. A Etapa 8 foi revisada e publicada sem emenda em
`20db6f021533230d791cd910b037554c3fe03191`; o fetch confirmou master, HEAD igual
a origin/master, árvore limpa e 0/0, com autoria e trailer preservados.
A Etapa 9 concluiu a verificação do pacote instalado e a revisão adversarial
final, com todos os gates aprovados. A publicação final ocorreu em `42cd2df`.
Em 2026-09-22 a Etapa 1 documental da Fase 9 foi concluída e aprovada:
especificação, threat model, decisões e rastreabilidade de façade PGWire,
múltiplos datasources e Admin UX v2. A Etapa 2 implementou modelos, store
cifrado, destino e migração explícita. Em 2026-09-23 a Etapa 3 foi autorizada e
implementou o registry multi-datasource, o coordenador interno e o lifecycle
fail-closed, ativados somente pelo composition root (D-087–D-091). Em 2026-09-24
a Etapa 4 implementou `/admin/v2` de datasources e o limite efetivo de DNS
(D-092–D-096), registrados somente com catálogo e Admin HTTP no composition
root. A especificação aprovada está em `docs/PHASE-9-SPEC.md`. As Etapas 5 e 6
foram concluídas e publicadas. A Etapa 7 está parcial, com quatro exceções
estreitas: a D-107 (commitada em `e9eb01a`), a D-108 (autorizada pelas
escolhas A1, B e C; validada; fechamento aprovado e publicação autorizada em
2026-10-07, com o estado de publicação confirmado pelo Git;
`docs/PHASE-9-STAGE-7-VALIDATION.md`, §1.4) e a D-109. Nesta, com aval do
usuário em 2026-10-08 a SCRAM-SHA-256, -PLUS sobre TLS, SASLprep e
`scramp==1.4.17`, e sob delegação das escolhas restantes, as peças puras do
startup PGWire (framing, credencial, SCRAM, channel binding) e a fixação de
`scramp`/`asn1crypto` foram implementadas localmente, sem commit e em revisão
independente. A validação integral foi medida em 2026-10-08: suíte com PG16
real verde, wheel e sdist com a sonda 54/54 (§1.5). A quarta é a D-110,
autorizada explicitamente em 2026-10-09: listener, TLS e autenticação sem SQL,
configuração externa, admissão e shutdown seguros, testes só em loopback, sem
deploy nem liberação de produção, runtime moderno como gate separado. Ela é
executada em lotes revisados: o lote 1 (`pgwire/settings.py` e
`pgwire/tls.py`), o lote 2 (`pgwire/transport.py` e `pgwire/driver.py`) e o
lote 3 (`pgwire/listener.py`) e o lote 4 (composição interna em
`build_application(pgwire=...)`) foram implementados localmente e revisados,
sem commit (§1.6). Os gates finais do lote 4 (2026-10-12: suíte integral e
`integration` com PG16 real, e wheel/sdist com sonda) passaram. O `main`
recusa `MASKGW_PGWIRE_ENABLED=1` (estado até 2026-10-14; em 2026-10-15 foi
autorizada só localmente a ativação sobre catálogo existente e sem Admin/UI,
com o lote 1 implementado e os gates medidos só no Windows, no runtime legado
3.11.3 e, em 2026-10-16, no CPython 3.14.8 temporário; ver a §1.6, lote 2c e
repetição moderna; POSIX não medido; fechado num commit local aprovado em
2026-10-16, sem push). Em 2026-10-16, localmente e em revisão: correção dos 4
`union-attr` de `datasource/destination.py` (mypy limpo; suíte integral de
5.329 sem falhas nos runtimes 3.11.3 e 3.14.8, só no Windows) e o desenho-proposta `docs/PHASE-9-STAGE-8-DESIGN.md`, não
aprovado; D-090 gate 2 aberta. O gate de runtime moderno foi medido em
2026-10-13 só no Windows com CPython 3.14.8 temporário (lotes A–C, §1.6):
suíte integral verde depois da correção só de teste dos casos NUL, e os 4
`union-attr` do mypy com o alvo 3.14 abertos. O lote C foi revisado. A
resolução limitada do hostname do bind foi implementada localmente em
2026-10-14, com medições finais no Windows nos runtimes legado e moderno
temporário (§1.6). Na mesma data o usuário aprovou fechar esse trabalho
validado num commit local, sem push; as menções a "sem commit" acima
descrevem o estado anterior. A ativação operacional, outra dependência, o bind
externo real, MCP multi-datasource e as Etapas 8–12 continuam sem execução ou
sem autorização. A D-090 segue aberta no gate 2, e a v2 proibida em operação
real. Evidência da Fase 8:
`docs/PHASE-8-STAGE-9-VALIDATION.md`; das Etapas 3 e 4:
`docs/PHASE-9-STAGE-3-VALIDATION.md` e `docs/PHASE-9-STAGE-4-VALIDATION.md`.

A UI agora recebe token explicitamente, valida metadados e DTOs e apresenta
seis vistas declarativas. Token somente na closure do transporte; navegação em
memória, limpeza no lifecycle e polling visível suspenso durante edição.
Adoção, config:validate, CRUD, reorder de regras e database/SQL aditivo exigem
gestos explícitos. Proteções efetivas readonly; fronteira HTTP da Etapa 4 intacta.
Leia `docs/PHASE-8-SPEC.md`, `docs/PHASE-8-TRACEABILITY.md` e a especificação
`docs/PHASE-9-SPEC.md`.

Antes de comecar qualquer fase, confira `git status --short`: a arvore precisa
estar limpa. **Confira, nao presuma** — este documento nao pode afirmar o
estado do working tree no momento em que voce o le.

Ordem de leitura sugerida:

| documento | para que |
|---|---|
| `CLAUDE.md` | invariantes e pipeline; carregado em toda sessao |
| **este arquivo** | estado, como rodar, o que fazer a seguir |
| `docs/ARCHITECTURE.md` | modulos e responsabilidades |
| `docs/SECURITY.md` | invariantes de seguranca e o que exigir antes de expor |
| `docs/SECURITY-REVIEW.md` | 11 findings do red team, seis fechados |
| `docs/DECISIONS.md` | D-001 a D-119, com o motivo de cada uma |
| `docs/MASKING-SPEC.md` | semantica exata do pipeline |
| `docs/TEST-PLAN.md` | o que cada camada de teste cobre |
| `docs/THREAT-MODEL.md` | cenarios de ataque e o resultado medido |
| `docs/FUTURE-HARDENING.md` | propostas avaliadas, com custo e impacto |
| `docs/ROADMAP.md` | histórico e estado das fases |
| `docs/PHASE-9-SPEC.md` | especificação aprovada de PGWire, multi-datasource e UX v2 |

---

## 1. Fases concluidas

**FASE 1 — Config Loader + Masking Engine puro.** Concluida.
**FASE 2 — PostgreSQL Adapter + ResultSet Masking.** Concluida.
**FASE 3 — Column provenance / lineage.** Concluida.
**FASE 4 — SQL validation + execution safety.** Concluida.
**FASE 5 — Gateway + MCP Server.** Concluida.
**FASE 6 — Security red team + hardening.** Concluida.
**FASE 6.1 — Fechamento dos bypasses criticos.** Concluida.

**As fases historicas 1–6.1 estao concluidas.**

Entregue na Fase 6.1:

- `sql/sensitivity.py`: analise de sensitividade por AST, uma vez por consulta
- F-01 (expressoes), F-02 (UNION + alias) e F-08 (exception via alias) FECHADOS
- H-1 corrigido: `mode` default das exceptions passou a `exact`
- 96 testes novos (1304 no total)

Histórico das etapas concluídas da Fase 7:

| etapa | estado | commit |
|---|---|---|
| 1 — IDs e revision no modelo do arquivo | concluida | `053cf66` |
| 2 — `RuntimeRegistry` | concluida | `3114c14` |
| 3 — runtime adquirido/liberado por query | concluida | `3c8de4c` |
| 4 — composition root e lifecycle | concluida | `7c06132` |
| 5 — filesystem seguro: verificações, lock exclusivo, escrita atômica, digest e limpeza de temporários | concluida | `d651fe0` |
| 6 — secao critica administrativa e fluxo completo de escrita/reload | concluida | `git log -- src/maskgw/admin` |
| 7 — aplicacao HTTP: auth, bind, anti-CSRF, headers, limites, handlers, rotas de leitura | concluida | `git log -- src/maskgw/admin/http` |
| 8 — `POST /admin/v1/config:validate` | concluida | `git log -- src/maskgw/admin/http/validate.py` |
| 9 — rotas de escrita e adocao com backup | concluida | `git log -- src/maskgw/admin/http/mutations.py` |
| 10 — `AdminAudit` | concluida | `git log -- src/maskgw/admin/http/audit.py` |
| 11 — suite adversarial administrativa | concluida | `git log -- tests/test_admin_adversarial.py` |

**A Fase 7 esta CONCLUIDA:** as onze etapas fecharam, e a suite adversarial da
Etapa 11 nao encontrou finding novo — cada cenario e `BLOCKED`, e os limites
conhecidos continuam afirmados por teste (D-041).

O estado atual deve ser conferido com `git status --short --branch` e
`git rev-list --left-right --count origin/master...HEAD` antes de continuar;
nao o presuma a partir deste documento versionado.

## 2. Stack e dependencias

Python >= 3.11.

| Pacote | Uso | Desde |
|---|---|---|
| psycopg[binary] | driver PostgreSQL | Fase 2 |
| pydantic | validacao de configuracao | Fase 1 |
| PyYAML | leitura do `masking.yaml` | Fase 1 |
| pytest | testes | Fase 1 |
| ruff | lint + format | Fase 1 |
| mypy | type-check strict | Fase 1 |

| pglast | parser oficial do PostgreSQL | Fase 4 |
| mcp | SDK MCP oficial, linha v2 (testado em 2.1.1) | Fase 5 |
| fastapi | fronteira HTTP administrativa (testado em 0.141.1) | Fase 7, Etapa 7 |
| uvicorn | servidor ASGI da Admin API (testado em 0.52.4) | Fase 7, Etapa 7 |
| cryptography | AES-256-GCM, HKDF e HMAC do catálogo | Fase 9, Etapa 2 (`50.0.1`) |

FastAPI e uvicorn sao usados **exclusivamente** pelo plano administrativo. O
MCP continua stdio only (D-036), e nenhuma porta e aberta sem
`MASKGW_ADMIN_ENABLED=1`.

Configuracao em `pyproject.toml`. Nao ha instalacao editavel: o pytest resolve
o pacote via `pythonpath = ["src"]`.

### Ambiente

O `.venv/` versionado ao lado deste repositorio foi criado no **Windows**
(`C:\Users\...`, Python 3.11.3) e nao funciona em macOS ou Linux. Ele esta em
`.gitignore` e nao deve ser usado como referencia.

Recrie o ambiente a partir do `pyproject.toml`:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Comandos (ajuste `.venv/bin` para `.venv/Scripts` no Windows):

```bash
.venv/bin/python -m pytest
```

```bash
.venv/bin/python -m ruff check src tests && .venv/bin/python -m ruff format --check src tests
```

```bash
.venv/bin/python -m mypy src tests
```

### Variaveis de ambiente

| Variavel | Uso | Obrigatoria? |
|---|---|---|
| `MASKGW_HMAC_KEY` | chave do `hmac_sha256`, minimo 32 caracteres | sim, se alguma regra usar `hmac_sha256` |
| `MASKGW_DATABASE_DSN` | DSN do PostgreSQL do Gateway | sim |
| `MASKGW_CONFIG` | outro `masking.yaml` (default: `config/masking.yaml`) | nao |
| `MASKGW_TEST_DSN` | DSN do PostgreSQL dos testes de integracao | nao; sem ela os testes `integration` dao SKIP |
| `MASKGW_ADMIN_ENABLED` | `1` habilita a Admin API; **qualquer outro valor nao habilita** | nao; default desligado |
| `MASKGW_ADMIN_TOKEN` | token administrativo, minimo 32 caracteres | sim, se a Admin API estiver habilitada |
| `MASKGW_ADMIN_BIND` | `127.0.0.1` (default), `::1` ou `localhost` — **so loopback** | nao |
| `MASKGW_ADMIN_PORT` | porta da Admin API, 1..65535 (default `8765`) | nao |

Nenhum usuario, senha, host ou DSN esta escrito no codigo ou nos testes.

Para rodar a integracao com um PostgreSQL descartavel em Docker:

```bash
docker run -d --name maskgw-pg -e POSTGRES_PASSWORD="$(openssl rand -base64 24)" -e POSTGRES_DB=maskgw_test -p 55432:5432 postgres:16-alpine
```

Depois exporte `MASKGW_TEST_DSN` apontando para ele. Testcontainers foi
deliberadamente **nao** adotado.

## 3. Arquitetura consolidada

```text
AI Client -> MCP Server -> Gateway -> Query Validator -> DB Adapter -> PostgreSQL
   (stdio)                                (Fase 4)          (Fase 2)
                                                              |
                                              Result Set + Column Metadata
                                                              |
                       MaskingEngine (Derived -> Exception -> Masking -> Original)
                                                              |
                                                        MaskedResult
```

Pipeline por coluna, default **ALLOW**:

```text
DERIVED (a AST provou dependencia sensivel) -> TRANSFORMER
EXCEPTION (pelo nome autoritativo)           -> ORIGINAL
MASKING (por output_name ou origin_name)     -> TRANSFORMER
NO MATCH                                     -> ORIGINAL
```

Desde a Fase 3 o matching avalia `output_name` OR `origin_name`, com
`origin_name` resolvido a partir da metadata do PostgreSQL. Desde a Fase 6.1,
uma dependencia sensivel provada pela AST vem antes das exceptions; fora desse
ramo, o default ALLOW e a prioridade das exceptions sobre masking permanecem.

## 4. Estrutura dos modulos

```text
src/maskgw/
  errors.py              ConfigError, TransformerError, DatabaseError
  secretsource.py        SecretProvider, EnvSecretProvider, MappingSecretProvider
  config/
    models.py            modelos Pydantic (extra="forbid", frozen)
    loader.py            load_config, load_config_text, parse_config
  masking/               <- nucleo PURO: sem banco, MCP, rede ou psycopg
    descriptor.py        ColumnDescriptor
    canonical.py         canonicalize  (Fase 2, D-015)
    rules.py             MatchMode, MatchSpec, MaskingRule, MaskingException, MaskingPolicy
    matcher.py           RuleMatcher, ExceptionMatcher
    engine.py            Action, Decision, MaskingEngine
    transformers/        base, params, registry, hashes, regex, randomize, simple
  db/                    <- Fases 2, 3 e 4
    columns.py           ColumnOrigin, describe_columns
    provenance.py        ftable/ftablecol -> catalogo -> origem  (Fase 3)
    capabilities.py      check_provenance_capability             (Fase 4)
    result.py            MaskedResult (+ truncated)
    sanitize.py          psycopg.Error -> DatabaseError / QueryTimeout
    postgres.py          PostgresAdapter: read-only, timeout, row limit
  sql/                   <- Fases 4 e 6.1
    parser.py            pglast; um statement executavel
    validator.py         allowlist de nos da AST
    policy.py            politica de funcoes e de relacoes
    sensitivity.py       dependencia sensivel por posicao  (Fase 6.1)
  gateway/               <- Fase 5
    models.py            QueryResult, QueryColumn, ErrorCategory, GatewayError
    service.py           Gateway.query: a fachada publica; run_audited compartilhado
    datasources.py       sessao por alias sobre o mesmo pipeline (Fase 9, Etapa 3)
  runtime/               <- Fase 7, Etapas 2 e 3; Fase 9, Etapa 3
    registry.py          RuntimeRegistry: acquire/release, retired, close unico
    candidate.py         candidato de datasource: destino, policy, limites, verificacao
    datasources.py       DatasourceRegistry: geracoes, sessoes, limites, drenagem
    datasource_service.py startup fail-closed e coordenador interno (sem HTTP)
  datasource/            <- Fase 9, Etapa 2: modelos, destino, store cifrado, migracao
    resolver.py          DNS em processo filho com prazo de 5 s (Fase 9, Etapa 4, D-092)
  admin/                 <- Fase 7, Etapa 6; a secao critica, SEM HTTP
    errors.py            AdminError e as categorias fechadas (10.2 + D-056)
    document.py          MaskingFileConfig <-> bytes YAML, round-trip conferido
    service.py           AdminConfigService: a secao critica e a secao 7.4
    http/                <- Fase 7, Etapas 7, 8 e 9; leitura + validate + escrita
      settings.py        enable, token, bind e porta: o passo 1 do startup
      middleware.py      Host, Origin, limite de corpo (413 autoritativo), auth, CT
      responses.py       forma unica de erro; categoria -> status HTTP
      schemas.py         modelos de resposta e de request, extra="forbid"/frozen
      views.py           respostas de leitura a partir de UM snapshot (D-057)
      validate.py        config:validate: valida e compila, SEM efeito (Etapa 8)
      mutations.py       o payload de cada escrita: MaskingFileConfig -> Mapping (Etapa 9, D-059)
      audit.py           instrumentacao: um AdminAudit por operacao (Etapa 10, D-060)
      app.py             8 leituras, config:validate e as 11 escritas + handlers
      server.py          uvicorn em thread nao-daemon, com bind confirmado
      v2/                <- Fase 9, Etapa 4: /admin/v2 de datasources, so com catalogo
        errors.py        vocabulario de erro proprio (D-095)
        schemas.py       corpos fechados, senha write-only, sem DSN pronto
        operations.py    traducao para o coordenador; leitura de UM snapshot
        audit.py         um DatasourceAdminAudit por operacao que alcanca o handler
        routes.py        inventario literal: 4 leituras (GET/HEAD) e 9 escritas
  bootstrap/             <- Fase 7, Etapas 4, 6 e 7; composition root
    application.py       construcao e lifecycle ordenado dos dois planos
    main.py              entrypoint compartilhado, stderr sanitizado
  __main__.py            python -m maskgw -> bootstrap
  mcp/                   <- Fase 5
    server.py            build_mcp_server; a tool query_database
    __main__.py          python -m maskgw.mcp -> bootstrap
  audit/                 <- Fase 5, ampliado na Fase 7 / Etapa 10
    log.py               QueryAudit, AdminAudit, AuditLog; UNICO modulo que importa logging
    datasource.py        DatasourceAdminAudit fechado da v2 (Fase 9, Etapa 4), sem logging

tests/
  conftest.py                    fixtures, DSN e dublês de conexao/cursor
  test_config_loader.py     35   test_canonical.py             52
  test_matching.py          44   test_db_columns.py            13
  test_transformers.py      94   test_db_masking.py            55
  test_engine.py            36   test_db_errors.py             38
  test_purity.py            32   test_db_leakage.py            46
  test_leakage.py           13   test_db_integration.py        80
  test_config_hazards.py     8   test_db_provenance.py         36
  test_config_gateway.py    33   test_pgresult_metadata.py     27
                                 test_sql_parser.py            36
                                 test_sql_validator.py        149
                                 test_execution_safety.py      48
                                 test_gateway.py               46
                                 test_mcp_server.py            54
                                 test_mcp_integration.py       43
                                 test_audit.py                 19

  test_sensitivity.py       54   <- Fase 6.1

  test_config_ids.py             <- Fase 7, Etapa 1
  test_runtime_registry.py       <- Fase 7, Etapa 2
  test_gateway_runtime.py        <- Fase 7, Etapa 3
  test_bootstrap.py              <- Fase 7, Etapas 4 e 6
  test_plan_separation.py        <- Fase 7, Etapas 4 e 6
  test_config_filesystem.py      <- Fase 7, Etapa 5
  test_admin_service.py     47   <- Fase 7, Etapa 6

  admin_http_support.py          <- Fase 7, Etapa 7 (apoio, nao e teste)
  test_admin_http_settings.py    51
  test_admin_http_boundary.py    88
  test_admin_http_surface.py    108
  test_admin_http_reads.py       64
  test_admin_http_lifecycle.py   35
  test_admin_http_leakage.py     20
  test_admin_http_mcp_coexistence.py  5  (integration)

  test_datasource_catalog.py     <- Fase 9, Etapa 2
  datasource_runtime_support.py  <- Fase 9, Etapa 3 (apoio, nao e teste)
  test_datasource_registry.py              <- Fase 9, Etapa 3
  test_datasource_runtime_service.py       <- Fase 9, Etapa 3
  test_datasource_runtime_integration.py   <- Fase 9, Etapa 3 (integration)
  test_datasource_bootstrap.py             <- Fase 9, Etapa 3
  admin_v2_support.py            <- Fase 9, Etapa 4 (apoio, nao e teste)
  test_datasource_resolver.py              <- Fase 9, Etapa 4 (D-092)
  test_datasource_service_v2.py            <- Fase 9, Etapa 4 (D-094)
  test_admin_v2_http.py                    <- Fase 9, Etapa 4
  test_admin_v2_audit.py                   <- Fase 9, Etapa 4 (D-095)
  test_admin_v2_concurrency.py             <- Fase 9, Etapa 4
  test_admin_v2_lifecycle.py               <- Fase 9, Etapa 4
  test_admin_v2_integration.py             <- Fase 9, Etapa 4 (integration)

  security/                      <- Fases 6 e 6.1, 209 testes adversariais
    test_attack_expressions.py        55
    test_attack_union_views.py        29
    test_attack_functions_catalog.py  29
    test_attack_oracle_errors.py      23
    test_attack_protocol.py           73
```

Os testes de protocolo MCP usam o cliente in-memory do SDK
(`mcp.Client(server)`), nunca a funcao Python decorada.

`tests/test_pgresult_metadata.py` nao testa codigo do Gateway: mede o que o
PostgreSQL e o psycopg devolvem. Se uma versao futura mudar esse contrato, ele
quebra antes do resto.

`masking/` continua puro: `test_purity.py` verifica por AST e em subprocesso
que importar `maskgw.masking` nao carrega `maskgw.db` nem psycopg, e a
contraprova confirma que `maskgw.db` de fato depende de psycopg.

Todos os modulos previstos ate a Etapa 6 existem: `masking/`, `config/`, `db/`,
`sql/`, `gateway/`, `runtime/`, `admin/`, `bootstrap/`, `mcp/` e `audit/`.

`gateway/factory.py` foi removido: construcao e lifecycle pertencem somente ao
composition root `bootstrap/`. A Etapa 5 adicionou `config/filesystem.py`, sem
HTTP: validacao fail-closed, lock sidecar pelo lifecycle, digest exato, escrita
atomica e limpeza seletiva de temporarios. A Etapa 6 adicionou `maskgw/admin/`,
tambem sem HTTP: a secao critica administrativa e o fluxo de escrita/reload.

A Etapa 7 adicionou `maskgw/admin/http/`, **somente leitura**: as oito rotas
`GET`/`HEAD` sob `/admin/v1`, autenticacao por bearer token, bind so em
loopback, anti-CSRF, limite de corpo, headers e os tres handlers de erro.
FastAPI e uvicorn entraram no `pyproject.toml` **agora**, e sao usados so ali.

O confinamento e estrutural e e teste com contraprova: importar `maskgw.admin`
**nao** carrega FastAPI, e importar `maskgw.admin.http` carrega. A secao critica
continua utilizavel — e testavel — sem servidor.

## 5. Decisoes

D-001 a D-014 na Fase 1; D-015 a D-019 na Fase 2. Detalhamento em
`docs/DECISIONS.md`.

| # | Decisao |
|---|---|
| D-015 | Canonicalizacao explicita por tipo, nunca `str()`; tipo desconhecido falha fechado. Emenda D-011 |
| D-016 | `autocommit=True` mais rollback defensivo; nunca COMMIT como limpeza |
| D-017 | Erro sanitizado levantado FORA do `except`, para zerar tambem `__context__` |
| D-018 | Leitura em lotes com `fetchmany`; nao e row limiting |
| D-019 | SQLSTATE classifica internamente, mas nao entra na mensagem |
| D-020 | `DERIVED` (o PostgreSQL afirma) e `UNKNOWN` (nos admitimos) sao distintos |
| D-021 | Cache `(oid, attnum)` por conexao; falha NAO e cacheada |
| D-022 | View resolve para a coluna da view; sem lineage recursivo |
| D-023 | Proveniencia resolvida antes de qualquer linha ser lida |
| D-024 | `origin_schema`/`origin_table` sao auditoria, nao criterio de matching |
| D-025 | Falha de proveniencia nao muda a politica; nao ha nova regra fail-closed |
| D-026 | Capability check de proveniencia, fatal no startup |
| D-027 | Funcoes: namespace `pg_` deny-by-default; resto allow com denylist |
| D-028 | Read-only e timeout por `options` do DSN, conferidos apos conectar |
| D-029 | Duas portas no adapter: `execute_validated` e `execute` sem validacao |
| D-030 | Row limit devolve ate `max_rows` e marca `truncated`; N+1 descartada |
| D-031 | Validacao por tipo de no da AST, incluindo `*Stmt` aninhados |
| D-032 | Erros de parser e validator nao citam a consulta |
| D-033 | Proveniencia nao sai para o cliente MCP |
| D-034 | Uma conexao, aberta no startup; sem pool; consultas serializadas |
| D-035 | Auditoria por `request_id`; digest da SQL descartado (oraculo) |
| D-036 | Somente stdio; nenhuma porta de rede |
| D-037 | Argumentos extras sao IGNORADOS pelo SDK, nao recusados |
| D-038 | Erro do MCP: categoria fixa, mensagem curta, sem encadeamento |
| D-039 | Relacoes de estatistica (`pg_stats`) bloqueadas no validator |
| D-040 | Falha de resolucao rejeita a consulta; `DERIVED` nao. Emenda D-025 |
| D-041 | Bypass conhecido vira teste que o AFIRMA, nunca `skip` |
| D-042 | Exception responde pelo nome AUTORITATIVO; alias nao cria excecao |
| D-043 | Sensitividade por AST aplicada ao resultado da expressao; ambiguidade recusa |
| D-044 | Serializacao de linha inteira (`row_to_json`) e recusada |
| D-045 | `mode` default das exceptions passa a `exact`. Corrige H-1 |
| D-046 | Um passo entre niveis: nomes exportados por CTE e subquery |

D-047 a D-054 foram aprovadas antes da Fase 7; comportamento das Etapas 8–11
continua ausente. D-055 registra escolhas de implementacao da Etapa 6, D-056 as
da Etapa 7, e D-057 as duas correcoes exigidas na revisao da Etapa 7:

| # | Estado na Etapa 7 |
|---|---|
| D-047 | `LoadedConfig` preserva juntos o modelo validado do arquivo e os objetos runtime compilados; o admin so escreve a partir do modelo validado |
| D-048 | Fluxo completo implementado: validar, construir, conectar, persistir, trocar — com as semanticas dos dois lados do `os.replace` |
| D-049 | Separacao de planos imposta e verificada por AST; `admin/` nao executa SQL e nao conhece `gateway/` nem `mcp/` |
| D-050 | Protecoes estruturais preservadas; nao ha superficie que as edite |
| D-051 | IDs estaveis implementados; com `revision >= 1`, ID ausente falha no carregamento |
| D-052 | Secao critica administrativa implementada: adocao, `expected_revision`, digest, limite de aposentados, persistencia e swap sob um lock |
| D-053 | `enabled` continua ausente |
| D-054 | `RuntimeRegistry` implementa refcount, `retired` e fechamento unico; o fluxo administrativo respeita os tres |
| D-055 | Runtime candidato construido do documento reparseado dos bytes que serao persistidos; callback e leitura administrativa recebem copia profunda, nunca o documento do runtime publicado; vocabulario de erro proprio do admin; `admin_enabled` como parametro de composicao |
| D-056 | Escolhas da fronteira HTTP: cinco categorias de erro novas, ordem dos middlewares, contencao da excecao por fora do Starlette, bind na thread chamadora, parametros de transformer no registry e contadores de `/status`. Aprovada como decisao de contrato na revisao da Etapa 7 |
| D-057 | Snapshot administrativo coerente (`AdminSnapshot`, uma leitura por resposta); shutdown SEM timeout, com `join` integral da thread HTTP; referencia do servidor adotada antes de `start()`; `_closing` permanente, que impede `run()` e nunca se apresenta como `ready` |
| D-058 | Contrato de `config:validate` (Etapa 8): request e o documento candidato na raiz com schema HTTP proprio; `expected_revision` no corpo -> `422 SCHEMA_INVALID`; resposta de sucesso sao quatro booleanos; falha de compilacao -> `CONFIG_INVALID`; sem efeito, provado por contadores estruturais; correcao do `BodyLimitMiddleware` para cortar em `413` autoritativamente sob o roteador do FastAPI |
| D-059 | Escrita administrativa (Etapa 9): toda rota traduz para `apply()`, mutacao dentro da secao critica sobre copia profunda (sem TOCTOU); IDs sao identidade do servidor; `allowed_pg_functions` presente em qualquer forma -> `IMMUTABLE_FIELD`; backup byte a byte da adocao com `O_EXCL`/`0600`/`fsync`, nunca sobrescreve, relogio injetavel |
| D-060 | Auditoria administrativa (Etapa 10): `AdminAudit` fechado por construcao com os nove campos da §13.2; uma entrada por operacao que ALCANCA o handler, nenhuma para leitura/recusa-de-fronteira/schema; `revision_before` observada dentro da secao critica via `AdminAuditProbe` (sem TOCTOU nem segunda publicacao); `target_id` so ID canonico de alvo unico; best-effort no logger; `audit/` continua o unico a importar `logging`; sem `GET /admin/v1/audit` |

## 6. Resultado das verificacoes

Medido ao final da Etapa 5, com `MASKGW_TEST_DSN` apontando para PostgreSQL
16.15 descartavel:

```text
pytest   1418 passed, 8 skipped condicionais de plataforma (1426 coletados)
pytest    408 passed, 1018 deselected  (-m integration)
          405 testes dependentes de DSN executados; nenhum skip por falta de DSN
pytest    209 passed  (tests/security)
```

Medido ao final da Etapa 6, com `MASKGW_TEST_DSN` apontando para um
PostgreSQL 16.15 descartavel em Docker:

```text
pytest   1485 passed, 9 skipped  (1494 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           9 skips condicionais de plataforma
pytest    410 passed, 0 skipped  (-m integration)
pytest      2 passed  (TestRealReload, o reload contra banco real)
pytest     93 passed, 1 skipped  (admin + bootstrap + plan separation)
           repetido 10 vezes sem intermitencia
pytest     16 testes de concorrencia, isolamento e reload real repetidos 15
           vezes, sem intermitencia
ruff     All checks passed
ruff     93 files already formatted  (src + tests)
mypy     Success: no issues found in 93 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 7, com `MASKGW_TEST_DSN` apontando para um
PostgreSQL 16.15 descartavel em Docker:

```text
pytest   1871 passed, 9 skipped  (1880 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os MESMOS 9 skips condicionais de plataforma do baseline
pytest    415 passed, 0 skipped  (-m integration)
pytest    371 testes novos da Etapa 7
           os arquivos HTTP repetidos 9+ vezes sem intermitencia
ruff     All checks passed
ruff     109 files already formatted  (src + tests)
mypy     Success: no issues found in 109 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 8 (ja com a correcao de D-058 — adotado sem ID como
`SCHEMA_INVALID` e escalares estritos), contra PostgreSQL 16.15 descartavel:

```text
pytest   1986 passed, 9 skipped  (1995 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os MESMOS 9 skips condicionais de plataforma do baseline
pytest    415 passed, 0 skipped  (-m integration)
pytest     80 testes de config:validate (61 da entrega + 19 da correcao D-058)
ruff     All checks passed
ruff     112 files already formatted  (src + tests)
mypy     Success: no issues found in 112 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 9, ja com as duas rodadas corretivas (as onze rotas de
escrita, a adocao com backup, e as correcoes das duas revisoes), contra
PostgreSQL 16.15 descartavel:

```text
pytest   2111 passed, 10 skipped  (2121 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os 9 skips condicionais de plataforma do baseline, mais 1 skip novo:
           o teste POSIX de fsync de diretorio falho, que no Windows nao se
           aplica — a omissao do fsync e afirmada por um teste-par proprio
pytest    485 passed, 1 skipped  (-m integration)
           o unico skip e o teste POSIX de fsync de diretorio, condicional de
           plataforma; nenhum skip por ausencia de DSN
pytest    129 testes da Etapa 9: 69 de escrita/adocao (test_admin_http_writes.py),
           58 adversariais (test_admin_http_writes_adversarial.py) e 2 e2e pela
           porta HTTP admin real (test_admin_http_writes_e2e.py)
ruff     All checks passed
ruff     116 files already formatted  (src + tests)
mypy     Success: no issues found in 116 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 10 (auditoria administrativa), contra PostgreSQL 16.15
descartavel:

```text
pytest   2267 passed, 7 skipped  (2274 coletados; JUnit XML)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os 7 skips sao condicionais de plataforma POSIX neste host Windows:
           tres de fsync de diretorio de durabilidade (writes, admin service e a
           nova auditoria de durabilidade), tres de bits de permissao POSIX do
           filesystem e um de fsync de diretorio do filesystem
pytest    521 passed, 2 skipped  (-m integration, 523 selecionados; JUnit XML)
           os 2 skips sao POSIX de fsync de diretorio, condicionais de
           plataforma; nenhum skip por ausencia de DSN
pytest    153 testes da Etapa 10: 77 de unidade (test_admin_audit.py, com a
           paridade de enums, o mapping fechado e a paridade CATEGORY_OUTCOME <->
           STATUS_BY_CATEGORY), 39 de fechamento real (test_admin_audit_closed.py —
           as contraprovas de schema fechado e as regressoes de coerencia
           outcome/categoria e de revisoes exatas), 36 de instrumentacao HTTP
           contra PostgreSQL real (test_admin_http_audit.py) e 1 de stdout MCP
           limpo sob auditoria (test_admin_http_mcp_coexistence.py)
ruff     All checks passed
ruff     120 files already formatted  (src + tests)
mypy     Success: no issues found in 120 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

A rodada corretiva de seguranca fechou o schema de verdade: `AdminAudit` guarda
os enums (nao strings), com validacao incontornavel em `__post_init__`;
`error_category` e o enum neutro `AdminErrorCategoryName`; o desfecho tem de bater
com a faixa de status da categoria (`CATEGORY_OUTCOME`); e as revisoes de sucesso
e de durabilidade sao exatas (`before + 1`). As classificacoes vivem no modulo
neutro `audit/`, com paridade provada por teste, sem ciclo. Detalhes em D-060.

Medido ao final da Etapa 11 (suite adversarial administrativa, ja com a rodada
corretiva), contra PostgreSQL 16 real:

```text
pytest   2304 passed, 8 skipped  (2312 coletados; JUnit XML)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os 8 skips condicionais de plataforma POSIX (os 7 anteriores mais a
           leakage de durabilidade da Etapa 11, POSIX-only)
pytest    558 passed, 3 skipped  (-m integration, 561 selecionados; JUnit XML)
           os 3 skips sao POSIX de fsync de diretorio; nenhum skip por falta de DSN
pytest    38 testes da Etapa 11 (test_admin_adversarial.py, integration; 37
           executados + 1 skip POSIX): leakage em todo grupo de erro de escrita
           (inclusive durabilidade DEPOIS do replace) e no AdminAudit; categoria
           exata em CONFIG_RELOAD_ERROR; imutabilidade adversarial; corpo hostil
           sem efeito e SEM construir candidato; IDs e decisoes de masking
           preservados sob ataque; concorrencia com estado/auditoria coerentes e
           sem leakage. A matriz de rastreabilidade §12.6-§12.8 esta em TEST-PLAN.
ruff     All checks passed
ruff     121 files already formatted  (src + tests)
mypy     Success: no issues found in 121 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

A Etapa 11 nao encontrou finding novo: cada cenario e `BLOCKED`, e os limites
conhecidos (payload gigante, ACL no Windows, editor nao cooperante) continuam
afirmados por teste (D-041). Nenhuma correcao de producao foi necessaria.

**A suite integral exigiu pilha ampliada neste host.** Com a pilha default do
Windows, `test_large_query_payload_does_not_crash` — a consulta com 100.000
termos somados — estoura a pilha da thread no walk recursivo da AST e derruba o
interpretador com `Windows fatal exception: stack overflow`. Nao e regressao:
reproduz identicamente no commit `d276c22`, anterior a Etapa 6. Nunca havia
aparecido aqui porque, sem DSN, esse teste dava SKIP.

O gate foi fechado rodando o processo de teste com pilha de thread de
**64 MiB**, valor que bastou. Nada foi deselecionado, pulado ou alterado no
teste, e **nenhuma correcao de producao foi feita**: a limitacao continua
aberta, na secao 11 e em `docs/SECURITY-REVIEW.md`.

```bash
.venv/Scripts/python.exe -c "import threading, pytest; threading.stack_size(64 * 1024 * 1024); raise SystemExit(pytest.main(['-q']))"
```

Na medição histórica da Etapa 6, os nove skips condicionais do host Windows
foram quatro criacoes de symlink sem
privilegio, tres verificacoes de bits POSIX e dois `fsync` de diretorio POSIX
(um do filesystem, um do fluxo administrativo). Os testes Windows reais,
inclusive `msvcrt` entre processos e a omissao de `fsync` de diretorio,
passaram.

Nao ha distribuicao WSL neste host; os ramos POSIX permanecem na suite
condicional para execucao nativa em POSIX.

## 7. Protecao contra alias: o que a Fase 3 fechou

`SELECT cpf AS documento` agora retorna **mascarado**. Cobertos e verificados
contra banco real:

| cenario | resultado |
|---|---|
| `SELECT cpf AS documento` | mascarado |
| alias dentro de subquery | mascarado |
| alias dentro de CTE | mascarado |
| alias sobre JOIN | mascarado |
| alias sobre cast (`cpf::text AS documento`) | mascarado |
| alias sobre view | mascarado (`provenance_kind = VIEW`) |
| `SELECT *`, nomes duplicados | cada posicao com origem propria |
| identificador entre aspas / maiusculas | mascarado |

## 8. Proveniencia: o que o PostgreSQL informa, e o que resta aberto

Medidas, nao supostas (`tests/test_pgresult_metadata.py`).

| cenario | `ftable` | efeito |
|---|---|---|
| coluna direta, alias, `SELECT *`, JOIN | oid da relacao | origem resolvida |
| subquery, alias em subquery, CTE, cast | oid da relacao | origem resolvida |
| view | **oid da VIEW** | origem e a coluna DA VIEW |
| **UNION** | **0** | sem origem |
| expressao, literal, agregado | 0 | sem origem (esperado) |

A tabela acima descreve o que o PostgreSQL informa, e continua valendo. O que
mudou e o que o Gateway FAZ quando ele nao informa nada:

- **UNION e expressoes deixaram de vazar.** A analise de AST da Fase 6.1
  (`sql/sensitivity.py`) cobre os dois casos: `SELECT substr(cpf,1,3) AS x` e
  `SELECT cpf AS documento FROM a UNION ALL SELECT 'x'` saem mascarados
  (D-043). Ambiguidade entre regras e serializacao de linha inteira sao
  rejeitadas.
- **View que renomeia continua aberta.** `CREATE VIEW v AS SELECT cpf AS
  documento FROM cliente` da `origin_name = "documento"`, e a definicao da view
  nao esta na arvore da consulta. Nem a AST nem a proveniencia enxergam `cpf`.
  Sem lineage recursivo por `pg_get_viewdef` (D-022, F-03).
- **Falha de catalogo em runtime REJEITA a consulta.** Nao e mais tolerante:
  D-040 emendou D-025. Havia proveniencia que deveria ser resolvivel, e
  devolver o resultado assim entregaria em claro uma coluna que deveria estar
  mascarada. `DERIVED` (`ftable = 0`) continua sendo estado legitimo e segue o
  fluxo normal; falha operacional levanta `CapabilityError`, que chega ao
  cliente como `CONFIGURATION_ERROR` sanitizado. O check de startup (D-026)
  cobre a instalacao; este cobre o runtime.

## 8b. Configuracao nova da Fase 4

```yaml
database:
  statement_timeout_ms: 30000   # 100 .. 600000
  max_rows: 1000                # 1 .. 1000000
sql:
  allowed_pg_functions: []      # acrescenta a allowlist do namespace pg_
  denied_functions: []          # acrescenta a denylist; a negacao vence
```

Ambas as secoes sao opcionais e validadas fail-closed. DSN e credenciais
continuam fora do `masking.yaml`: declarar `password`, `dsn` ou `host` ali e
erro fatal, nao campo ignorado.

`load_config` continua devolvendo so a `MaskingPolicy`; `load_gateway_config`
devolve tambem `database` e `sql`.

## 9. Sondagem para a Fase 4

`SELECT 1 AS a; SELECT 2 AS b` **e aceito** pelo psycopg3 quando a consulta nao
leva parametros: o protocolo simples permite multiplos statements, `fetchall()`
devolve o primeiro result set e `nextset()` retorna `True`. Com parametros o
protocolo estendido rejeita (`cannot insert multiple commands into a prepared
statement`).

Ou seja: **o bloqueio de multiplos statements da Fase 4 e obrigatorio** e nao
pode depender do driver. Ate la o adapter e componente interno, sem superficie
MCP.

Ponto de atencao herdado da Fase 3 (D-023): a proveniencia e resolvida com um
cursor proprio na mesma conexao, antes do primeiro `fetchmany`. Isso e seguro
com o cursor client-side do psycopg3, que ja materializou o resultado. Se o row
limit da Fase 4 introduzir cursor server-side, essa ordem precisa ser
reavaliada.

## 9b. Como subir o servidor MCP

```bash
export MASKGW_HMAC_KEY="<chave com ao menos 32 caracteres>"
export MASKGW_DATABASE_DSN="host=... dbname=... user=... password=..."
python -m maskgw.mcp
```

`MASKGW_CONFIG` aponta outro `masking.yaml` (default: `config/masking.yaml`).

Transporte de dados: **stdio**. Falha em qualquer passo do startup termina o
processo com codigo 1, e o servidor nunca fica disponivel parcialmente
funcional.

**Sem `MASKGW_ADMIN_ENABLED=1`, nenhuma porta e aberta** — o processo e
exatamente o de antes da Etapa 7: nenhuma thread nova, nenhum lock de arquivo e
nenhum caminho de escrita.

### 9b.1 Como subir tambem a Admin API (opcional, Etapa 7)

```bash
export MASKGW_ADMIN_ENABLED=1
export MASKGW_ADMIN_TOKEN="<token com ao menos 32 caracteres>"
python -m maskgw.mcp
```

`MASKGW_ADMIN_BIND` (default `127.0.0.1`) aceita **so** `127.0.0.1`, `::1` e
`localhost`; `MASKGW_ADMIN_PORT` default `8765`. Bind fora de loopback, token
ausente ou curto, porta invalida e porta ocupada **impedem o startup** — e o
MCP nunca fica disponivel.

Leitura, com o token no header e so nele:

```bash
curl -H "Authorization: Bearer $MASKGW_ADMIN_TOKEN" http://127.0.0.1:8765/admin/v1/status
```

As oito rotas sao `GET`/`HEAD`: `status`, `config`, `rules`, `rules/{id}`,
`exceptions`, `exceptions/{id}`, `transformers` e `protected`. **Nao ha escrita
nesta etapa**, nao ha `/docs` e nao ha CORS. Token em query string ou cookie
nunca e aceito, e `Origin`/`Referer` presentes recusam a requisicao com `403`.

O startup anuncia host e porta em `stderr`; `stdout` continua exclusivamente
com o protocolo MCP.

## 9c. Postura de seguranca (leia antes de expor)

`docs/SECURITY-REVIEW.md` traz os 11 findings: **seis corrigidos**, cinco
aceitos. Os tres bypasses de uma linha de SQL foram fechados na Fase 6.1.

**Obrigatorio antes de expor:** revogar `EXECUTE` das funcoes de usuario para a
role do Gateway. `EXECUTE` e concedido a `PUBLIC` por padrao, e uma funcao
pre-existente que leia coluna sensivel devolve o valor sob o nome dela (F-04).

```sql
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

**Permanece aceito e nao fechado:**

- oraculo por predicado reconstroi um CPF em 11 consultas (F-07), fora do
  escopo do MVP
- view que renomeia coluna sensivel expoe o valor (F-03)
- default ALLOW: coluna sensivel com nome fora do padrao passa em claro

Conclusao: com o `EXECUTE` revogado e o oraculo aceito, **uso interno com
cliente semi-confiavel**. Nao adequado a exposicao externa — o transporte de
dados e stdio e nao ha autenticacao nele.

**A Admin API da Etapa 7 nao muda essa conclusao.** Ela e loopback-only, sem
TLS, com um token estatico e um unico papel; autentica o plano administrativo,
e nao o plano de dados. Antes de habilita-la:

- o token e um segredo de verdade: 32+ caracteres, de `MASKGW_ADMIN_TOKEN`, e
  nunca em linha de comando, onde apareceria em `ps`;
- quem alcanca `127.0.0.1` alcanca a porta. Numa maquina multiusuario, isso
  inclui outros usuarios locais;
- rotacao e trocar a variavel e reiniciar. Nao ha endpoint que rotacione
  secret, e nao havera.

## 9d. Mudancas de comportamento da Fase 6.1

Tres, todas documentadas e cobertas por teste:

1. **Exception nao e mais alcancavel por alias** (D-042). `SELECT cpf AS
   tipo_cpf` passou de original para mascarado. `SELECT tipo_cpf` nao mudou.
2. **Expressoes sobre coluna sensivel sao mascaradas ou recusadas** (D-043).
   `concat(cpf, email)` e `row_to_json(c)` passaram a ser recusadas.
3. **`mode` default das exceptions e `exact`** (D-045). Configuracao que
   dependa de exception por substring precisa declarar `mode: contains`.

## 9e. Mudancas de comportamento da Etapa 7

Uma so, e ela e opcional:

1. **Existe uma porta de rede, quando pedida.** Com `MASKGW_ADMIN_ENABLED=1` o
   processo passa a abrir um socket em loopback e a manter uma thread HTTP
   nao-daemon. **Sem a variavel, nada muda** — nenhuma porta, nenhuma thread,
   nenhum lock de arquivo —, e isso e teste, inclusive num processo real.

Mudancas internas que nao alteram comportamento observavel do MCP:

- `TransformerRegistry.register` aceita os nomes dos parametros de cada
  transformer, para que `GET /admin/v1/transformers` os publique a partir de uma
  fonte unica (D-056). Chamadas existentes continuam validas;
- `RuntimeRegistry` conta aquisicoes, e `AdminConfigService` conta operacoes
  administrativas, para os contadores de `/status`. Sao inteiros em memoria, nao
  historico, e **nao** antecipam `AdminAudit`;
- `AdminConfigService.snapshot()` devolve `AdminSnapshot` — `revision`,
  documento e `SqlPolicy` de UMA leitura do runtime publicado — e as funcoes de
  `views.py` passam a receber esse snapshot em vez do servico (D-057). As
  propriedades `revision`, `adopted`, `document` e `sql_policy` continuam
  existindo para leitura avulsa; o que nao se pode e combinar duas delas na
  mesma resposta;
- `AdminHttpServer.stop()` **bloqueia ate a thread HTTP terminar**: nao ha mais
  `shutdown_timeout`, e o limite passou para o `timeout_graceful_shutdown` do
  uvicorn, que encerra requisicoes arrastadas para que a thread sempre chegue ao
  fim (D-057). No caminho normal nada muda;
- o composition root adota a referencia do servidor ANTES de `start()`
  (`_build_admin_http` constroi sem iniciar), e `Application` ganhou `_closing`
  permanente: `run()` recusa uma aplicacao em desmontagem e `repr()` reporta
  `closing` em vez de `ready` (D-057);
- piso do uvicorn subiu para `>=0.29`, versao em que
  `timeout_graceful_shutdown` existe.

## 10. Como continuar

As Fases 7 e 8 estão **CONCLUÍDAS** e publicadas. A Etapa 1 documental da Fase 9
foi concluída e aprovada em 2026-09-22. A Etapa 2 foi autorizada nesta sessão e
implementou somente o pacote interno descrito em
`docs/PHASE-9-STAGE-2-DESIGN.md`; as Etapas 3–12 ainda exigem revisão e
autorização próprias.

### A. Endurecer o que resta (inventario preservado; nao e a proxima etapa)

Os dois findings HIGH abertos nao precisam de codigo:

- **F-04** — revogar `EXECUTE` das funcoes de usuario para a role do Gateway.
  E operacional, e esta na secao 9c. Deveria ser feito antes de qualquer uso
  real, e nao depende de mais nenhuma fase.
- **F-07** — decidir formalmente se o oraculo por predicado e aceitavel para o
  contexto de uso, ou restringir o uso.

Os que precisam de codigo, com custo em `docs/FUTURE-HARDENING.md`:

| item | esforco | observacao |
|---|---|---|
| F-03 lineage de view por `pg_get_viewdef` | medio | exige reparsear a definicao e mapear posicoes |
| F-04 resolver `FuncCall` em `pg_proc` | medio | gestao de funcoes do PostgreSQL |
| `unmatched_policy: allow \| mask \| deny` | pequeno | evolucao natural do default ALLOW; muda a filosofia, precisa de aprovacao |
| F-07 controle de inferencia | grande | e outro produto |

### B. Fase 7 — Admin API

```text
Fase encerrada:
Fase 7 — Admin API, CONCLUIDA (Etapas 1–11)

Entrega concluída, revisada e aprovada:
Fase 8 — Etapas 1–9 aprovadas e publicadas em `42cd2df`.
Fase 9 — ETAPA 3 IMPLEMENTADA LOCALMENTE (registry e lifecycle); PGWire, Admin v2 e UI v2 não iniciados.
```

A Etapa 5 concluiu os primitivos de filesystem seguro em
`config/filesystem.py`: arquivo/diretorio/lock verificados, lock exclusivo
mantido aberto, SHA-256 dos bytes exatos, duas verificacoes de digest, escrita
atomica e limpeza estrita de orfaos.

A Etapa 6 criou `maskgw/admin/` — `errors.py`, `document.py` e `service.py` — e
com ele a secao critica administrativa. `AdminConfigService.apply` executa os
onze passos da secao 7.4 sob **um** lock por processo, e o composition root
passa a adquirir o `ConfigFileStore` quando o admin esta habilitado, mantendo-o
ate o shutdown. O runtime inicial e construido dos bytes do snapshot lido sob o
lock, para que o digest de referencia corresponda ao runtime publicado.

A Etapa 7 criou `maskgw/admin/http/` e a fronteira de rede: as oito rotas de
leitura, autenticacao por bearer token em header, bind so em loopback, as
quatro camadas anti-CSRF, o limite de 1 MiB que corta streaming, os headers
obrigatorios e os tres handlers de erro. O admin passa a ser habilitado por
`MASKGW_ADMIN_ENABLED=1`, e nao mais so por parametro de composicao.

`build_application` tem agora **dois** parametros administrativos, e a
distincao importa: `admin_enabled` compoe a secao critica — lock e caminho de
escrita —, e `admin_http` acrescenta a fronteira HTTP — thread, socket e rotas.
O segundo implica o primeiro, nunca o contrario. `resolve_admin_settings()` le
o ambiente e e o passo 1 do startup, antes de qualquer arquivo ser aberto.

A Etapa 9 acrescentou as onze rotas de escrita, a operacao `config:adopt`
completa (IDs aleatorios, `confirm_comment_loss` e backup byte a byte dos bytes
originais) e `IMMUTABLE_FIELD`. Cada rota e so uma traducao para
`AdminConfigService.apply()`, com a mutacao rodando DENTRO da secao critica sobre
a copia profunda do documento corrente (D-059).

A Etapa 10 acrescentou a **auditoria administrativa** (`admin/http/audit.py` e
`AdminAudit` em `audit/`): `config:validate` e cada uma das onze escritas que
alcanca o handler emitem exatamente um `AdminAudit` pelo `AuditLog` injetado —
o MESMO do plano MCP. `admin/` e `admin/http/` continuam sem importar `logging`;
`audit/` segue sendo o unico autorizado, e isso e teste. `revision_before` e a
revision observada DENTRO da secao critica, via `AdminAuditProbe` preenchido por
`apply` — sem TOCTOU, sem segunda publicacao, sem alterar a ordem dos onze passos
(D-060). Nao ha `GET /admin/v1/audit`, nem store, retencao ou consulta de
historico; o conjunto de rotas permanece o da Etapa 9.

A Etapa 11 fechou a **suite adversarial administrativa** (§12.6–§12.8). Comecou
por uma matriz de rastreabilidade de cada requisito contra os testes existentes
(em `docs/TEST-PLAN.md`) e acrescentou so as lacunas reais, em
`tests/test_admin_adversarial.py`: leakage em todo grupo de erro de escrita
(inclusive falhas injetadas antes/depois de `os.replace`) e no `AdminAudit`,
`__cause__`/`__context__` nulos num `AdminError` real, imutabilidade por
alias/aninhamento/mistura, corpo hostil sem efeito nem auditoria, e concorrencia
preservando estado, serializacao, auditoria e sigilo. Todos `BLOCKED`; nenhum
finding virou `skip`/`xfail`.

A especificacao aprovada esta em `docs/PHASE-7-SPEC.md`.
Ela cobre endpoints, autenticacao, bind e CORS, schemas, IDs e migracao,
revision e 409, persistencia atomica, lifecycle dos runtimes, sanitizacao de
erro, secrets, protecoes read-only, testes exigidos e escopo de auditoria.

As quatro questoes que estavam abertas foram decididas (secao 14.1 da spec):

| questao | decisao |
|---|---|
| `allowed_pg_functions` | somente leitura na Admin API; loader nao muda nesta fase |
| runtimes aposentados | limite 1; `409 RELOAD_BUSY` antes de construir o candidato |
| porta default | 8765 |
| comentarios do YAML | perda aceita, com backup dos bytes originais |

Dez bloqueios da revisao tambem foram corrigidos na especificacao, entre eles: `config:reload`
removido da primeira versao, `409 CONFIG_OUT_OF_SYNC` antes de toda escrita,
`CONFIG_DURABILITY_ERROR` com `applied: true` para falha de `fsync` depois do
`replace`, lock exclusivo de arquivo contra um segundo processo, bind so em
loopback, e uma composition root em `bootstrap/` que e o unico modulo autorizado
a conhecer os dois planos. A composition root foi implementada na Etapa 4, o
filesystem na Etapa 5, a serializacao com as duas verificacoes de digest e a
semantica de durabilidade na Etapa 6, e os itens de HTTP — bind so em loopback,
porta e autenticacao — na Etapa 7.

Todas as onze etapas foram concluidas; a Fase 7 esta fechada.

Objetivo: superficie administrativa separada do MCP para gerenciar
configuracao, policies, status e auditoria sem editar arquivo a mao.

**Principios ja aprovados** — decididos antes de qualquer codigo, registrados
em D-047 a D-054 com o motivo de cada um:

- Admin API **completamente separada** do MCP: planos distintos, sem handler e
  sem schema compartilhado
- Admin API **nao executa SQL**. Nao havera `/query`, `/sql` nem `/execute`
  (D-049)
- **MCP continua sendo o unico caminho de query**, e nunca altera configuracao
- **Secrets nunca retornados**, nem parcialmente mascarados: so `configured` /
  `missing`
- **A fonte administrativa persistida e o arquivo de configuracao validado**,
  nao os objetos runtime compilados (D-047)
- **Mudanca constroi runtime novo por inteiro** (D-048)
- **Runtime nunca e alterado parcialmente**: a query ve o antigo inteiro ou o
  novo inteiro
- **Persistencia atomica** e **troca de runtime atomica**, nesta ordem:
  validar → construir runtime → conectar e verificar → persistir → trocar
  (D-048). As duas sao atomicas **separadamente**: nao ha atomicidade conjunta
  entre filesystem e memoria
- **Depois do `rename` o arquivo ja e o novo**, e nao ha rollback de arquivo.
  Falha da persistencia preserva o arquivo anterior; falha antes dela preserva
  arquivo e runtime (D-048)
- **Janela de crash entre persistir e trocar**: se o processo morrer nela, o
  disco tem a configuracao nova — ja validada e ja comprovada conectavel — e o
  proximo start sobe com ela. Uma operacao que nao retornou sucesso pode ter
  tomado efeito no restart (D-048)
- **O DSN nao e campo administrativo**: credenciais, host e banco continuam
  vindo so de secret/env. A reconexao do candidato existe porque
  `statement_timeout_ms` viaja em `options` do DSN (D-028, D-048)
- **Ciclo de vida do runtime por refcount + `retired`** (D-054): o reload nao
  bloqueia esperando queries antigas; o runtime antigo e aposentado no swap; o
  ultimo release o fecha exatamente uma vez; se ja nao houver usuarios no
  swap, e fechado ali mesmo; e nenhuma query adquire um runtime aposentado
- **`revision` + `expected_revision`** para controle otimista de concorrencia,
  verificados **dentro de uma secao critica administrativa serializada**: duas
  requisicoes com o mesmo `expected_revision` nao vencem ambas (D-052)
- **Protecoes estruturais nao sao editaveis** — `denied_relations` com
  `pg_stats` e o caso concreto (D-050)
- IDs administrativos estaveis para rules e exceptions; a ordem continua
  semanticamente relevante (D-051)
- `enabled` fica fora da primeira versao (D-053)
- bind HTTP opcional em **`127.0.0.1`** por default, **sem CORS wildcard**
- **sem front-end** nesta fase

### C. Fase 8 — CONCLUÍDA; ETAPAS 1–9 REVISADAS E APROVADAS

Especificação: `docs/PHASE-8-SPEC.md`; matriz: `docs/PHASE-8-TRACEABILITY.md`;
evidência atual: `docs/PHASE-8-STAGE-9-VALIDATION.md`. D-061–D-064 vigentes.

A fonte bruta e a ordem de validação da Etapa 3 permanecem. Os bytes validados
são copiados para os handlers; nenhuma releitura em HTTP. A pilha original é
preservada com UI off (20 entradas/28 pares). UI on tem 24 entradas/36 pares:
HTML, JS e CSS públicos canônicos; `presentation.json` exige bearer.
Raw path, query, método e precedência seguem §§5.2–5.3; nenhuma montagem genérica.
Host/origem/Fetch Metadata são verificados antes do token; proxy headers ficam
explicitamente desligados nesse modo. Não há CORS, cookies ou redirecionamentos.

O ESM instala somente a entrada pública, sem pedidos administrativos. Após
entrada explícita, o transporte confere hash/gramática da apresentação e o
reader valida DTOs fechados, revisions seguras e envelopes coerentes. A sessão
é privada e o DOM usa somente criação explícita/texto. Logout/401/pagehide/
pageshow/BFCache cancelam leituras, invalidam geração e descartam referências.
Seis vistas e seleção apenas em memória; status a cada 15 s visível, serial,
com suspensão após falha e retry manual. Nenhuma tela invoca o POST abstrato
check retido para compatibilidade dos testes de transporte da Etapa 4.

Node 24.20.0 / npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e declarações
Node 24.0.0 seguem fixados. Chromium 153.0.8010.12 (1243), Firefox 155.0 (1543)
e WebKit 26.6 (2359) são reutilizados, sem atualização. Build termina antes
dos consumidores. Na Etapa 8, JS/CSS/apresentação e âncora mudam; modelos privados não mudam;
HTML, gramática, contratos de negócio e vocabulário permanecem intactos.

O coordenador genérico mantém base/rascunho/comando congelados, uma pendência e
releitura após confirmação. Erros são mapeados pela apresentação privada;
conflito conserva rascunho e exige revisão de base separada, busy só permite
nova tentativa manual, e durabilidade/resultado desconhecido continuam bloqueados.
O transporte projeta corpos fechados, valida template/identidade/modelos e nunca
recebe URL/método livres. `workbench.js` integra adoção, validação, CRUD de regras/exceptions, reorder de
regras, database e SQL aditivo. `author.js` constrói candidatos fechados da base
e do rascunho. A Etapa 9 comprovou a distribuição instalada e os critérios de
aceite, sem modificar o produto ou recursos gerados.

### D. Fase 9 — PGWire, múltiplos datasources e Admin UX v2 · ETAPA 3 LOCAL

A especificação aprovada `docs/PHASE-9-SPEC.md` define listener PostgreSQL para IDEs, alias
em `dbname`, autenticação separada, TLS externo, credenciais upstream cifradas,
registry multi-datasource e redesign da UI. Especificação, threat model,
decisões e rastreabilidade estão concluídos. O MCP permanece `stdio`;
Streamable HTTP/OAuth não fazem parte. A Etapa 2 adicionou somente o catálogo
interno e a validação de destino; não adicionou listener, registry, rota v2,
UI v2 ou publicação de runtime. Erro depois do replace do store tem resultado
incerto; uma rotação de master key interrompida é resolvida pelo procedimento
explícito de `docs/PHASE-9-STAGE-2-DESIGN.md` §6.4, com as duas chaves
preservadas. Rotação confirmada remove os backups cifrados com a chave anterior;
suspeita de comprometimento da chave exige também trocar as credenciais
upstream.

A Etapa 3 adicionou o runtime multi-datasource, ativado somente por
`build_application(datasource_catalog=DatasourceCatalogSettings(...))`
(D-087); nenhuma variável de ambiente o liga e o MCP continua no runtime legado
até a Etapa 11. Com o parâmetro, o startup abre o store, verifica cada
datasource habilitado (destino revalidado, policy compilada, conexão com
read-only, timeout e proveniência) e constrói o registry antes do legado, do
Admin HTTP e do MCP; um datasource habilitado inválido derruba tudo. Cada
sessão (`gateway/datasources.py`) captura uma geração e abre a própria conexão;
troca, desabilitação e remoção drenam sem mudar o destino da sessão. Limites
(D-089): por datasource `limits.max_sessions`, 1 aposentada e 1 candidato;
globais 32 sessões, 4 aposentadas e 2 candidatos. Limites efetivos de
timeout/linhas são o mínimo entre policy e limits (D-088). O coordenador
`DatasourceRuntimeService` testa o candidato antes de persistir e publicar, e o
teste de candidato não tem efeito (D-091). Evidência em
`docs/PHASE-9-STAGE-3-VALIDATION.md`. A matriz em
`docs/PHASE-9-TRACEABILITY.md` governa as Etapas 4–12.

Limitação da D-090, ainda NÃO corrigida: a resolução DNS ganhou teto na Etapa
4 (D-092), mas um candidato não tem prazo total. O `connect_timeout` cobre só o
estabelecimento da conexão; as consultas de verificação depois da autenticação
dependem do `statement_timeout` do próprio servidor, e um upstream que autentica
e para de responder prende o handler `async` da v2, o event loop administrativo
e o shutdown. Dois gates distintos: (1) limite efetivo da verificação
pós-conexão de candidatos antes da ativação da Admin v2 pelo operador (Etapa 7);
(2) limite de validação e masking locais antes dos ingressos PGWire (Etapa 8) e
MCP multi-datasource (Etapa 11). Nenhuma solução pode abandonar thread, processo
ou conexão, e o mecanismo exige decisão aprovada antes do código.

A Etapa 4 (2026-09-24, local, sem push) acrescentou `/admin/v2` de datasources
(D-092–D-096), registrada somente quando `build_application` recebe
`datasource_catalog` e `admin_http`; sem catálogo o app administrativo é a v1
byte a byte, e nenhuma variável de ambiente nova existe. Leituras sem segredo
(`credential: {configured: true}`, sem endereços fixados), criação, edição,
rotação de credencial, teste de rascunho e de persistido sem efeito,
habilitar/desabilitar, remoção com confirmação pelo alias e política por
datasource. Concorrência otimista por datasource; handlers síncronos no event
loop como na v1; vocabulário de erro e auditoria (`DatasourceAdminAudit`)
próprios. A resolução DNS roda num processo filho com prazo de 5 s, morto e
recolhido ao fim do prazo. O default do MCP foi adiado para a Etapa 11 (D-096).
Depois de uma falha de persistência o catálogo exige reinício: escritas e
leituras v2 respondem `503 CATALOG_BLOCKED`; `/admin/v2/status` segue em modo
degradado. Evidência em `docs/PHASE-9-STAGE-4-VALIDATION.md`.

A Etapa 5 (2026-09-24, local, sem push; D-097–D-100) trouxe a Admin UX v2
somente leitura: apresentação no formato 2 com as seções da v1 inalteradas
(selos da Etapa 8 preservados), barra lateral única com Painel, Datasources,
detalhe com abas, protótipo "Novo datasource" sem campos e o grupo Política v1
intacto. A UI só faz `GET` sob `/admin/v2/`; 404 e 503 viram estados
explicados; sem catálogo, a sessão cai na Visão geral da v1 como antes. Tema
claro/escuro sem storage. O vocabulário privado da v2 é verificado por token.
Um refinamento visual, emendado no mesmo commit, trouxe três mudanças. Em
telas estreitas a navegação fica atrás de um botão `Menu:` acessível. O
Painel foi hierarquizado. Os avisos ficaram curtos.
Capturas de referência (fixture sintética) em `docs/ux-v2/`, com o conjunto
anterior em `docs/ux-v2/antes/`, aprovados pelo usuário em 2026-09-28.

A Etapa 6 (autorizada em 2026-09-28, local, sem push; D-103–D-106) trouxe o CRUD
visual pelas nove escritas v2 da D-093: assistente de cadastro com teste do
rascunho, edição de conexão e limites, troca de senha, teste, habilitar/desabilitar,
remoção confirmada pelo alias e editor de política com ordem visível e reordenação
por teclado. A apresentação declara as ações em `console.actions`; o JS público
monta o corpo por caminho (`frontend/src/desk.js`) e envia só por
`client.submit`, com inventário exato conferido no Python, no verificador público
e no transporte. Uma escrita por vez, rascunho só em memória, revisão e
confirmação explícitas; conflito preserva o rascunho sem rebase; resposta perdida
ou resultado incerto bloqueiam novas escritas até uma leitura nova. O harness
`tests.browser_console_server` ganhou o modo de escrita (`MASKGW_BROWSER_WRITE=1`)
com falhas injetadas. Evidência em `docs/PHASE-9-STAGE-6-VALIDATION.md`. O limite
pós-conexão da D-090 continua aberto: a v2 segue ativável só pelo composition root. Toolchain fixada: Node 24.20.0/npm 11.19.0 locais; o `.venv`
contém uma instalação antiga e não editável de `maskgw`, por isso o harness de
navegador define `PYTHONPATH=src` no modo checkout. Evidência em
`docs/PHASE-9-STAGE-5-VALIDATION.md`.

### Fora do escopo, inalterado

RBAC, OAuth/OIDC, LDAP/SSO, multi-tenant, MySQL, pool transacional de
conexoes, `resources`/`prompts` MCP, schema discovery, JSONB deep inspection,
lineage completo, transformers Python customizados, column-level GRANT
automatico, banco de configuracao, Redis, background workers.

### Antes de iniciar a proxima etapa

- `git status --short` vazio: a arvore precisa estar limpa
- suíte completa e gates verdes, sem deselect; usar a medição atual em
  `docs/PHASE-8-STAGE-9-VALIDATION.md`, distinguindo-a dos registros históricos
- PostgreSQL 16 real disponível via `MASKGW_TEST_DSN`, sem nenhum skip por
  ausência de DSN; skips condicionais de plataforma discriminados na evidência
- Fase 8 publicada em `42cd2df`; a Etapa 1 documental da Fase 9 foi concluída e
  aprovada, a Etapa 2 foi concluída (`docs/PHASE-9-STAGE-2-VALIDATION.md`) e as
  Etapas 3 e 4 locais foram implementadas com evidência em
  `docs/PHASE-9-STAGE-3-VALIDATION.md` e `docs/PHASE-9-STAGE-4-VALIDATION.md`.
  As Etapas 5 e 6 foram publicadas, e a Etapa 7 está parcial (só as exceções
  D-107, D-108 e D-109, esta só com peças puras e sem commit; ver o topo deste
  documento). Nenhuma outra implementação
  funcional da Etapa 7 nem das Etapas 8–12 está autorizada sem revisão e
  aprovação próprias.
- neste host Windows, rode o pytest com pilha de thread ampliada (64 MiB), ou o
  teste de payload gigante derruba o processo. Nunca o transforme em `skip`
  (D-041); a limitacao esta na secao 11

## 11. Riscos conhecidos que atravessam qualquer fase seguinte

1. **Default ALLOW.** Coluna sensivel com nome fora do padrao passa em claro.
   E consequencia direta do modelo, nao um defeito, e a protecao depende da
   qualidade do `masking.yaml`.
2. **Funcao de usuario pre-existente** que leia coluna sensivel devolve o valor
   sob o nome dela (F-04). Mitigacao e privilegio, nao codigo.
3. **View que renomeia coluna sensivel** expoe o valor (F-03).
4. **Oraculo por predicado** reconstroi um CPF em 11 consultas (F-07).
5. **Cache de proveniencia por conexao** fica obsoleto apos `RENAME COLUMN`
   (D-021). O Gateway e read-only sobre schema estavel; nao ha invalidacao.
6. **Argumentos extras do MCP sao ignorados, nao recusados** pelo SDK 2.1.1
   (D-037). Nao alteram nada; a expectativa de recusa e que nao se cumpre.
7. **`audit/` e in-memory-free**: escreve via `logging`, sem storage proprio —
   tanto a auditoria de consulta (`QueryAudit`) quanto a administrativa
   (`AdminAudit`, Etapa 10). Nao ha historico consultavel e nao existe
   `GET /admin/v1/audit` — qualquer feature que precise disso comeca do zero.
8. **Consulta com dezenas de milhares de termos pode derrubar o processo.** A
   analise da AST e recursiva, e uma expressao com 100.000 somas estoura a
   pilha da thread antes de qualquer limite do produto. **Nao existe controle
   no Gateway** que limite o tamanho da consulta ou a profundidade da
   expressao: quem decide o desfecho e o tamanho de pilha disponivel. Com a
   pilha default deste host Windows o processo cai; com 64 MiB por thread o
   mesmo caso passa — foi assim que a suite integral fechou, e isso e
   propriedade do AMBIENTE DE TESTE, nunca uma protecao do produto.
   Nao e regressao da Fase 7 — reproduzido em `d276c22` — e **continua sem
   correcao**. Uma correcao real seria limitar o tamanho da consulta na
   fronteira, ou tornar o walk iterativo; as duas mudam comportamento ja
   entregue e precisam de aprovacao propria.

## 12. Armadilhas ja pisadas (nao repita)

Registradas porque custaram tempo e foram descobertas por teste, nao por
revisao:

- **`raise ... from None` nao basta.** Zera `__cause__`, mas o interpretador
  ainda pendura a excecao original em `__context__` quando o `raise` ocorre
  dentro de um handler ativo. Levante FORA do handler. Aconteceu duas vezes
  (D-017 na Fase 2, e de novo na Fase 6 em `provenance.py`).
- **`SELECT 1 INTO nova` parseia como `SelectStmt` e cria uma tabela.** Raiz
  SELECT nao basta (D-031).
- **`str()` sobre `memoryview` embute o endereco do objeto** e quebra o
  determinismo do HMAC em silencio (D-015).
- **Multiplos comandos com parametros** sao recusados pelo protocolo estendido
  do psycopg. Separe o DDL do INSERT parametrizado nas fixtures.
- **Descer a arvore inteira em cada nivel** tornou a analise de AST quadratica
  e travou o processo com 200 subqueries aninhadas (D-046). Use `Skip`.
- **`bool` e subclasse de `int`; `datetime` e subclasse de `date`.** A ordem
  dos `isinstance` na canonicalizacao importa (D-015).
- **Nomes de coluna duplicados sao validos.** Nunca indexar linhas por nome.

Regra do projeto: nao avancar de fase ou etapa sem aprovacao, nem com teste
falhando.

A fonte bruta em `bootstrap/settings.py` depende somente de stdlib; a resolução
e a checagem da dependência UI/Admin ficam em `bootstrap/application.py`,
preservando-o como único importador do plano administrativo no composition root.
