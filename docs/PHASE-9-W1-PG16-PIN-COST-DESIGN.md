# Custo dos pins do leitor PG16 — desenho do diagnóstico somente leitura

2026-10-31, sob delegação vigente. Entradaafaffad0 aceita58487/publicada em
0e370e4, Host8c41605f aceito61196. Nenhuma nova raiz operacional, estado,
comando de rodada, Docker/PG/shell/secret/worker ou serviço criado por este texto.
P2-4 de orçamento permanece aberto até medições e composição próprias.

## Incremento proposto

Novo `docs/poc/pg16_shell_pin_cost.py` e fakes, revistos antes de um diagnóstico
real. Capturar a entradaafaffad0 e seus dados/código por SHA, somente definições.
Não chamar prepare/admit/run/drive/start_cycle/start_supervision/perform_b,
nenhum start/close/emergency de watchdog, CLI/PowerShell, sampler de clock,
owner/bootstrap/identidade, install/commit ou função que escreva evidência.

Instanciar dois Hosts com estado diagnóstico **incompatível** com FRESH/INVOCADO do
ensaio, mas com task pública32hex, pins/blueprints23/delivery_plan exatos que
seu constructor requer. Path lógico inexistente sob REPO, só valor em memória;
não criar esse diretório, arquivo ou attempt. Context para final_pins recebe
entry_sha256 correto. Sem invocar a entrada, materializar raiz ou mudar Bstart.

Uma instância fica sem monitores (estimativa de admissão). Na outra, para
medir o pin transitivo completo, construir os23Stores/Watchdogs reais
diretamente, com as mesmas fontes fixadas do Host, na thread principal, em
paths lógicos sem mkdir. Constructors revisados só capturam definições/criam
objetos/locks/eventos; nunca start. Callback de aborto recusa por categoria
fechada e jamais é usado. Ao terminar, exigir todos `_started=False` e
`thread is None`; nenhum owner ou tarefa asyncio criado. Não usar namespace
fake no diagnóstico real nem confundir construção com medição de thread/OS.

As quatro operações medidas são exatamente:

1. Host.pins(cleanup=False), que relê os arquivos de fonte fixados.
2. Host.pins(cleanup=True), que verifica capturados/executáveis/configuração
   fixados sem as mesmas releituras de fontes.
3. Entrada.final_pins(context) sem monitores, como em prepare.
4. Entrada.final_pins(context) com23monitores, que inclui Host.pins normal
   e todos pins transitivos/stdlib, inclusive cópias das23policies.

Medir com perf_counter_ns monotônico, cinco ciclos na ordem normal/cleanup/
final0/final23, sem warmup adaptativo ou retry. Preservar todas20durações e max/mediana
calculados a partir delas; tempos estritamente positivos/contagens fechadas.
Registrar separadamente custo de construção de cada Host/context/23Watchdogs.
Startup/capturas já leem fontes antes das amostras: não chamar a primeira
amostra de cold-cache nem os máximos observados de pior caso do filesystem.
Número de leituras/tamanhos continua limitado pelos leitores/pins fixados;
latência síncrona do SO não tem teto absoluto por esse diagnóstico.

## Sigilo e saída

pins lê também os arquivos privados de configuração Docker já fixados no4bc.
O diagnóstico não publica conteúdo, caminhos absolutos, nomes de volumes,
variáveis, stdout de processo ou mensagem original de erro. Não instrumentar
R.pinned por monkeypatch, não copiar raw e não alterar funções consumidas.
O relatório projeta somente kind/versão, SHA das fontes públicas, identificação
do perfil, contagens, durações inteiras e estado fechado. Não apresentar hash
de configuração privada como nova evidência pública. Sem argv/root do operador.

Falha de pin/arquivo/clock/runtime vira NOT_PASSED e categoria enumerada, sem
str/repr/traceback/contexto. Nada parcial vira medição completa. Uma execução
do diagnóstico, sem repetir para eliminar amostra lenta. Saída JSON canônica
limitada16KiB, schema fechado e validada antes de ser persistida/publicada.
Sem logger novo ou recurso write de produção. O launcher de uma execução
Python própria/sem argumentos será proposto/revisado separadamente; este
incremento de código/fakes ainda não lê os executáveis/config reais.

## Limite da medição de admissão

Constructor/context/final_pins são parte do custo da admissão, mas esse
diagnóstico não chama admit nem lê uma raiz operacional. Portanto não afirma
ter medido o prepare completo≤3s. A verificação do limite3s e do estado≤32768
continua exigida no preparador/etapa própria, com raiz/bytes previamente
revisados e somente leitura antes de marcar INVOKED. Não criar uma raiz
antecipadamente apenas para alegar cumprimento do gate. Se a ordem precisar
de proposta em duas etapas (materialização/preflight e só depois invocação),
registrá-la sem chamar o diagnóstico parcial de admissão comprovada.

## Uso no orçamento, sem antecipar aceite

Contar CLIs/pins explícitos por caminho dos23casos e passos A/cleanup/restore,
com fakes para **contagem**, não tempo nativo. Somar contagem ao custo medido
de normal/cleanup e ao pin final/admissão. Incluir três WAIT≥24s, owner12/
shell8, attach/rm das amostras públicas anteriores só como insumos parciais,
inclusive cauda6,3s de rm. Estimativa típica e margem são explícitas (meta
recomendada≤70% deB300), sem afirmar que somar máximos individuais cabe.

Recalcular também atraso síncrono de um pins/join55, coleta31 e restore93,
mais custos de pins dos CLIs de cleanup/restore e janela600/655. Se não houver
margem, não propor matriz; revisar prospectivamente ou manter gate fechado.
Não ampliar12/8/600 ou reinterpretar uma rodada consumida NOT_PASSED. Primeiro
total real dos23casos poderá ser medido só na rodada proposta, nunca inventado
a partir desses tempos de leitura ou dos fakes.

## Fakes antes de medir

Provar whitelist exata de operações/capturas e ausência de chamada de efeito;
20amostras/ordem/estatísticas determinísticas; clock regressivo/tipo inválido/
falha intermediária/limite/schema não produzem resultado completo; erro com
str/repr hostil permanece fechado; nenhum path/secret/configuração ou partial
é exportado; constructors reais dos23Watchdogs com start que falha se chamado;
Host/context/flat/transitive pins ligados às fontes aceitas. Nenhum binário/
config real é lido por esses fakes. Depois revisão do helper e do comando exato
antes da única execução somente leitura, preservando resultado inclusive falha.

Exportador do ensaio, preparador, proposta nativa e rodada PG16 permanecem
posteriores. Oracle621/app/SQL/IDE/MCP/Gateway/produção não são alterados nem
liberados. Sem quota/job observado ou segundo escritor.

## Precisões8601 incorporadas antes do código

Claude2 aceitou a direção do desenho/fakes com seis precisões; não executou
nem liberou leitura real de configuração/binários ou qualquer rodada.

1. Depois dos constructors, a única mutação do Host diagnóstico é ligar os
   mapas `_stores`/`_monitors` à segunda instância. Nenhum global capturado
   é alterado. Argumentos do Watchdog são os mesmos de start_supervision:
   watch-NN lógico, Store, _cleanup_lock, callback inerte e os bytes pg_raw/
   captured nas mesmas posições. Comparar com construtor espião no fake do
   start_supervision real, sem executar suas ações no diagnóstico real.
2. Dois Hosts/Contexts separados, sem alternar atributos entre medições. Sem
   monitores mede os pins de prepare; com23, os pins terminais. Os modos pertencem
   a enum fechado; cinco ciclos intercalados,20amostras e construção separada.
3. Sem argumentos; uma linha JSON canônica≤16KiB, gravação só pelo launcher
   revisado. Runtime Windows3113/-I/-B/optimize0 conferido antes de qualquer
   captura, sem pycache criado. Fim exige threading.enumerate()==[main],
   nenhum loop criado e todos monitores _startedFalse/threadNone. Fakes
   espiam mkdir/openW/X/subprocess; path lógico fora de Temp, inexistente
   antes e depois, nunca publicado. Não chamar API que crie loop para checá-lo.
4. Saída só enum/durações inteiras/contagens e SHA públicos de host/entrada/
   SOURCES/TRANSITIVE_PINS. Nunca conteúdo/hash/caminho de config/META,
   stdout de executável ou texto de OSError. Estado kind diagnóstico próprio,
   sem phase/invoked, entry_sha256=afaffad0. Nenhuma execução de binário.
5. Falha intermediária gera somente NOT_PASSED/categoria, sem estatísticas
   parciais. Não descartar amostra lenta/repetir até passar. Max é observado,
   não pior caso. Resultado completo só depois das20amostras e pós-condições.
6. Fakes contam cada invoke.pins(cleanup), pins explícito por caso e antes
   do owner.start, separados em A/Bporcaso/tipo, coleta/retry e restore.
   Caminhos substituídos por fakes devem ter contribuição adicional declarada,
   sem apresentar contagem parcial como total. Tempos de fakes não entram.

Ordem8601: código/fakes/revisão; comando revisado/uma leitura; composição do
orçamento; preparador/materialização/estado. Não é exigida prévia de admit
em uma raiz separada: construção Host+Context+final0 estima a admissão, sem
alegar prepare completo medido. Se o máximo observado dessa soma passar de
cerca2s, rever antes da proposta. Prepare continua gate3s em execução.

Qualquer ADMISSION_TIME ou recusa anterior a INVOKED também consome a raiz:
não repetir na mesma raiz nem criar outra até passar sem revisão nova.
Materialização anterior à invocação não é admissão comprovada. Este texto
esclarece ENTRY-DESIGN sem mudar o código afaffad0 ou ampliar seus limites.
