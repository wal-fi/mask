# PG16 público — exportador por projeção, somente fakes

2026-10-30 sob delegação. Direção e precisões aceitas na revisão55166 antes
do código. Nenhuma raiz operacional PG16, DockerCLI, PS, container, PG/SQL,
seed ou credencial nova. Preparador02d1 não foi materializado em destino real.

## Fonte e escopo

`docs/poc/pg16_public_export.py`, SHA-256
`95f09bbbc04cdf9389d0b8621b3b2e0a49201928b7605c14b84761bbfbd1b6d1`.
Captura preparador02d1, entradaa608 e parsers/helpers pinados. Não chama
materialize/prepare/drive ou qualquer processo. Import só define funções.
Raw nunca é copiado: apenas summary.json construído e transport.json, nenhum
arquivo de origem publicado. Schema exato no desenho e no teste positivo.

Fonte plana de nome fechado/regular/não-reparse, máximo256 arquivos/4MiB por
arquivo/16MiB total. JSON sem duplicatas/NaN. Raiz/date/kind/pins/task/imagem/
medida fechados. Somente FINISHED/ABORTED e exit0/1 coerentes; HELD/FRESH/
INVOKED recusados. Owned cleanup/inventárioCID/Desktop/thread devem estar
positivos. Nenhuma categoria ou mensagem arbitrária de origem é publicada.

Ledger de comandos publica só label fechado/exit/bytes/hash. Replies CLI
ligados pela ordem dos comandos CLI no ledger, além de tamanho/hash/exit;
PS público filtrado por labels próprios. Índice, nome e disposition exatos.
Isso distingue respostas vazias ou iguais de operações diferentes. Brutos
info/version são descartados pelo host; o manifesto registra sua ausência.

Imagem readmitida pelo parser pinado, só PG_VERSION/presença e contagem de
labels OCI projetados. CID/identidade/intenção durável/read-only/limites/
superfície/mounts conferidos pelo perfil já aceito. grupos true somente com
aceitação completa; false no grupo da recusa, null sem atestação independente.
Recusa não vira sucesso. Estado pós-execução e owner são projetados quando
presentes; owner precisa CLOSED/NOT_SENT/released/role/cid coerentes. Não há
fase inventada na tentativa abortada sem case final.

Fatos do probe recalculados do raw inteiro e iguais ao relatório canônico.
Journal replayado com12 checkpoints para A→B, boot igual/intervalo/head
calculados. Categorias/origens só do vocabulário fechado da entrada.
Desktop inicial e estado de restauração devem concordar.

Volumes comparados por conjuntos reais capturados; baseline inteira e raw
local-* retidos. Metadados baseline/decision/final com schema/tipos fechados,
decisão concorda com Mounts do próprio CID e baseline, final com inventário
registrado. Modo incerto nunca é transformado em prova por flag falso. Hashes
e contagens públicos, nomes só anônimos novos64hex do próprio CID. Digests
servem para coerência, não sigilo de nomes previsíveis. Abort antes de admitir
volumes usa NOT_ADMITTED/null, sem inventar inventário vazio/restaurado.

Fontes rechecadas antes de criar destino novo. Escrita xb/flush/fsync; marker
transport.json.next promovido por rename só após persistência e conferência
dos dois arquivos públicos. Falha preserva parcial sem transport.json, não
apaga/sobrescreve/reexecuta. Falhas retornam código fechado fora do except,
sem texto original, cause ou context. Exportação não é autoridade de cleanup,
liberação de owner, certificação de origem criptográfica ou release.

## Testes e histórico

42passed em30,38s, Windows3.11.3, somente fluxo real da entrada com CLI/owner/
clock/monitor simulados e arquivos públicos de pytest. Inclui schema exato,
report/ciclo/ledger/imagem/perfil/volumes, abort diagnóstico e inventário não
admitido, perda de prova, adulterações, JSON/limites/reparse/fonte mudada,
destino existente, segredo sintético em campo arbitrário não copiado e falhas
de fsync/rename. Não houve subprocesso ou filesystem do SO Oracle por isso.

Primeira rodada10failed/17passed em19,64s: fixture omitia invokedtrue ao pular
a admissão. Corrigido só no harness, sem afrouxar o exportador. Depois:

- Duas regressões falharam no protótipo: inventário vazio confundido com
  ps vazio por hash e marker transport visível antes do fsync (2failed,
  1passed/24deselected em3,73s). Vínculo sequencial e marker temporário corrigem.
- Seleção seguinte27passed em18,83s.
- Cinco regressões novas falharam antes do fix: count booleano, Desktop
  contraditório, intent não confirmado, uncertain0 em vez de false e modo
  de volume desconhecido encoberto por flags falsas (5failed/27deselected,
  4,26s). Corrigidos os tipos/coerência/recomputação.32passed em31,28s.
- Dez casos de limites/reparse/JSON/rechecagem/falhas de persistência levaram
  aos42 atuais; escritos depois das guardas, não são vermelhos primeiro.

Ruff src/tests, format328 e mypy strict311/314326 limpos; lint restrito dos
dois helpers limpo. Runtime sóWindows3.11.3. Suíte PG integral/browser/pacotes
não repetidos porque produto/dependências não mudaram. Exportador isolado
aceito na revisão94684, sem bloqueador. Duas precisões não bloqueantes:

- post_execution_state é a última observação own-inspect após o report,
  normalmente a inspeção do cleanup após quiesce, não promessa de observação
  imediatamente após drain. O State e o index/sha da observação ficam no resumo.
- source_unchanged refere-se à reconferência imediatamente antes de mkdir do
  destino. Não atesta ausência de escrita posterior de terceiros. O conteúdo
  publicado é derivado do snapshot imutável capturado e validado; não autentica
  origem nem concede autoridade. Não há observador de filesystem em background.

Nenhuma fonte foi alterada por essas precisões. Proposta exata/estado/raiz/
comando e revisão continuam obrigatórios antes de qualquer rodada real.

Seleção final dos dez componentes:378passed em52,39s, sem skips/falhas/erros.
Código95f09bbb/preparo02d1 confirmados após os gates, sem alterações funcionais
desde os aceites. Somente documentação mudou no fechamento seguinte.
Gateway indisponível; B1/B2/D090/C1/SQL/serviço/produção continuam abertos.
