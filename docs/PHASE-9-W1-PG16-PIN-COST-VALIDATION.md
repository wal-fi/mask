# Diagnóstico de custo dos pins — implementação e fakes

2026-10-31, sob delegação vigente. Baseline1ae0a5b sincronizado, árvore
rastreada limpa e arquivos pessoais preservados. Desenho aceito8601 com seis
precisões incorporadas. Helper0195b1e4/12028bytes aceito pelo Claude2 em99073,
somente como helper/fakes isolados, sem execução sobre binários/configuração reais.

## Fonte e efeito

`docs/poc/pg16_shell_pin_cost.py` não captura entrada/Host ao importar. Main
recusa runtime/argumentos errados após importar só sys builtin, antes de
qualquer Python-file import/captura. Exige Windows3113/-I/-B/optimize0.
Captura entradaafaf e seus Host8c/dependências só depois dos gates.

Dois Hosts/Contexts com kind diagnóstico sem phase/invoked, task pública e
blueprints/plano exatos; um sem monitores, outro com23Stores/Watchdogs reais.
Únicas alterações posteriores dos Hosts são mapas de Stores/Watchdogs na
instância. Sem mudar globais consumidos, chamar start/close/emergency ou API
de lifecycle/CLI. Root lógico sob REPO ausente antes/depois, nenhum mkdir.
Nenhum owner/tarefa/Bstart. Enum de quatro modos, cinco ciclos intercalados:
NORMAL, CLEANUP, FINAL0, FINAL23.20amostras inteiras ns mais construção de
builders/HostContext0/HostContext23/monitores. Não declara cold-cache ou pior
caso do filesystem; stats são mediana e maior valor observado.

Quiet confere main único, política/loop ainda não criados por observação sem
API que os construa, monitores não iniciados/threadNone e nenhuma tarefa/owner.
Capturas leem só código público até os pins reais serem chamados. Os pins
então podem ler configuração privada fixada; saída não publica esse conteúdo,
hash ou caminho. Uma linha JSON canônica≤16KiB, só SHA públicos/durações/
contagens. Falha intermediária descarta tudo, sem estatística parcial. Erros
originais/str/repr/traceback não vão à saída. Falha/short-write de stdout
fecha o stream e retorna1, sem tentar aproveitar prefixo.

## Gates anteriores à revisão

-37testes próprios/11,61s, nenhuma falha/skip/deselected, sobre helper0195b1e4.
- Ruff src/tests e helper E9/F63/F7/F82 limpos; format339conformes e mypy336
  alvos3.11/3.14 aprovados. Runtime sóWindows3.11.3, não3.14.
- Construtores reais de dois Hosts/23Watchdogs, com espiões negando writes,
  mkdir, subprocessos e Thread.start. Root ausente. Argumentos comparados ao
  start_supervision real com root/mkdir/activate apenas simulados: root-NN,
  Store/snapshotBNone, lock próprio, callback inerte e mesmos cinco blobs nas
  mesmas posições. Essa referência cria loop do teste, não loop do diagnóstico.
- Clock regressivo/zero/bool/overflow, erro intermediário com str/repr hostil,
  runtime pré-import, schema/limite/contagens/ordem, stdout IO, quiet inesperado
  e dados privados recusados. Nenhum executável/config privado lido nos fakes.
- Dois casos de bool como inteiro falharam antes do fix:2failed/24passed/1,70s.
  host_counts e stats agora exigem tipos inteiros exatos antes de comparar.
- Dois casos stdout IO falharam primeiro:2failed/32deselected/0,44s. Refusa
  cedo e main final agora recolhem o stream/saem1 sem mensagem original.
- Estáticos iniciais apontaram só imports/fixtures e anotação de lista mista
  do clock fake, corrigidos. Sem ampliar5ciclos/16KiB nem limite de produto.

## Contagem de chamadas, não medição de latência

`tests/test_pg16_shell_pin_counts.py` exercita três caminhos reais do código
do Host/entrada com transportes simulados: Desktop preservado, restore próprio
e falha com mutex/fire/join/retry e restore próprio. Pins de invoke e explícitos
do loop/case são observados; caminhos PS/clock/final substituídos são declarados
separadamente. Não há soma silenciosa de chamada fake com tempo nativo.

| Caminho | Chamadas observadas de Host.pins |
| --- | --- |
| A |1normal explícito +6normal dos CLIs |
| B, cada caso |1normal do loop +1normal antes do owner +4normal de invoke |
| Coleta B, cada caso |4cleanup de invoke |
| Coleta global positiva |2cleanup de invoke |
| Restore preservado |1cleanup de invoke |
| Restore próprio |3cleanup de invoke |
| Primeira coleta com mutex ocupado no cenário de retry |0invoke, sem supor categoria exportada pelo Host |
| Coleta depois de fire/join positivo |6cleanup por record +2cleanup globais |

Complementos **não executados nativamente**: A tem12PS normais,12pins cleanup
do sample e12leituras próprias do clock tratadas separadamente como subconjunto
para estimativa conservadora; restore preservado1PS cleanup, próprio2PS cleanup
e1sample/clock. Partida própria de Desktop em A não foi executada nesse modelo
e tem1PS normal adicional declarado. Restore com10polls exigirá somar até9PS
extras antes da proposta. Final23 foi substituído uma vez, prepare/final0 não
faz parte do run de contexto pré-construído. Owner.start real inclui seu guard
de pins dentro da janela12s, conforme C._opened antes de admit_runtime; esses
fakes não medem esse custo nem o attach/shell e não provam conclusão emB300.

Os23casos são agrupados por categoria (quatro positivos/noveHEADER/trêsDEADLINE
e restantes), não por tempo fake. O teste de retry segura lock próprio, deixa
a primeira coleta falhar e só libera no join da emergência fake, antes de uma
nova coleta dos mesmos records. Nenhum CID real ou cleanup paralelo criado.

## Fechamento99073

Fonte final0195b1e43353167b24f8e66606450e7beeea1e7d2daddcdeec9f6d95b9b12bd8,
12028bytes, aprovada99073 sem P1/P2 de implementação.37próprios/11,61s e
seleção final dos11arquivos pin-cost/pin-counts/entry/host e componentes:
399passed/104,82s, nenhuma falha/skip/deselected. Ruff/helper/format339 e
mypy336 alvos3.11/3.14 limpos; runtime sóWindows3.11.3. Fonte não mudou
depois dos gates/revisão; apenas documentos de estado/evidência.

Precisões para a conta futura: coleta com RunningTrue pode acrescentar kill
e reinspect (+2cleanup); restore próprio pode precisar de10process-polls,
chegando a cerca15pins de cleanup, e retry repete coleta. A compilação de
bounded nos paths PS/clock está fora dos pins e precisa de contribuição
separada/conservadora. FINAL0+HostContext0 estima admissão; FINAL23 é terminal,
monitors23 é anterior a A e não custo B. Emergência usa outra thread e pins
próprios, fora destas contagens: o limite1s de pin é conferido depois da
leitura no54cc, não teto absoluto de latência de filesystem.

Nenhum tempo de fake é promovido a medição real. Próxima leitura requer
comando/ambiente/cwd/pins/captura/validação/evidência próprios revisados e
uma execução, sem descartar outlier ou repetir falha. Nenhuma revisão ativa,
quota/job novo ou segundo escritor. Este aceite não abre orçamento/produção.

## Limites e próxima etapa

Não há comando de medição/proposta/launcher
novo, nenhuma medição real de pins, estimativa de latência ou admissão3s
comprovada. Construtores/fakes leem apenas fontes públicas do repo. Ainda faltam
revisão do comando e única leitura real, composição por caminho/margem e custo
pósB incluindo hashes/600/655; depois preparador/estado/proposta/rodada.

Saída MEASURED do helper não significa orçamento aprovado, bootstrap passado,
query ou produção. Configuração Docker privada continua local; futuras falhas
de pin não autorizam relaxá-lo ou repetir medição até passar. Oracle/app/SQL/
Gateway não foram alterados. B1/B2/D090/C1/produção continuam abertos, sem
quota/job novo, revisão duplicada ou segundo escritor.
