# Etapa 8 — medir imports reais no laboratório Linux

**2026-10-21, sob delegação; proposta de execução a revisar pelo Claude2.**
Não é worker, implantação, certificação de plataforma ou liberação SQL.
O diagnóstico AS anterior permanece congelado, com seus quatro resultados
e limites. Esta medição não substitui seus 32 MiB nem aprova B-2.

## Pergunta e dois casos, uma rodada

Importar, sem conectar ou instanciar serviço, nesta ordem fechada:
`maskgw.db.postgres`, `maskgw.runtime.snapshot`,
`maskgw.pgwire.result_encoder`. Isso exerce código e dependências reais
do caminho futuro, não imports do MCP/Admin/aplicação completa.
Os passos são **cumulativos**, incluindo `__init__` de db/config/runtime/
datasource e seus imports transitivos (inclusive cryptography nativo), não
custos isolados dos três módulos. Registrar delta de `sys.modules` de cada
passo, distribuição e caminho relativo de cada módulo, sem truncar prova:
se exceder relatório, coleta inconclusiva. Proibidos: mcp, fastapi, starlette,
uvicorn, anyio, scramp, asn1crypto e maskgw.admin/bootstrap/mcp. Aparecimento
invalida a montagem. Conferir threads/fds/processos por passo: filho,
socket ou thread nova invalida a montagem.
O harness escolhido é mais estrito: qualquer mudança no conjunto de fds
persistentes por etapa invalida o controle, mesmo se não for socket. Não
relaxar essa regra depois de ver os resultados.
Registrar VM inicial, início/fim de cada import, VmSize/VmPeak/VmRSS,
threads, inventário e métricas cgroup antes/depois; sem imprimir exceções
nativas, configurações, ambiente ou dados de banco.

1. Controle sem AS, ainda sob domínio externo finito: imports completos
   devem funcionar para que o perfil instalado seja considerado válido.
2. Mesmo perfil com soft=hard RLIMIT_AS de **32 MiB** no supervisor antes
   do spawn. Conferir limite efetivo no membro antes de GO, como no
   diagnóstico anterior. Não configurar limite abaixo do VmSize inicial:
   preflight <=28 MiB no supervisor e membro. Nenhum ajuste até verde.

Membro emite start/end de cada etapa em linhas limitadas; supervisor
registra o último start/end e returncode inclusive negativo se houver morte
nativa. MemoryError/ImportError/sinal no caso limitado, **só se o controle
passou as mesmas etapas**, pode ser registrado como did_not_fit, sem
atribuir causa ao AS; outra falha é inconclusiva. Um limite de memória pode
abortar Rust em vez de gerar exceção Python; não perder esse resultado.
OOM, erro de import, sinal ou deadline não são resultado aprovado. Registrar
qual etapa começou/terminou e a falha em categoria fechada; erro de extensão
nativa não implica automaticamente que a causa foi AS. Se o controle não
carregar, não executar o caso limitado. Se o limitado falhar ou não couber,
registrar incompatível/inconclusivo, sem repetir ou aumentar cotas nesta
rodada. `imports_fit_as32` só pode ser true com todos os imports e pico
do membro <=33.554.432, com conjunto de módulos igual ao controle. Sucesso
de import não prova espaço para query/AST.

## Instalação de laboratório, sem alterar produto/host

- Mesma imagem oficial Python mínima, já fixada e obtida no lote anterior:
  `python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590`,
  Linux amd64/Python 3.11.17. Inspecionar novamente, não usar tag flutuante.
- Wheel puro do produto medido na D-115, hash
  `de45edb1c8ea30bbccd9ef73cb9533c7d705fd1ade76cdb926f90a60c4b45449`,
  só após comparar seus membros de produto aos fontes atuais. Não copiar
  checkout inteiro, .venv, configurações, .git ou credenciais.
- Wheelhouse temporário fora do checkout, somente binários Linux/pure Python
  do PyPI oficial, versões iguais às já instaladas no host: pglast 8.4,
  psycopg/psycopg-binary 3.3.4, pydantic 2.13.5/pydantic-core 2.46.5,
  PyYAML 6.0.3, cryptography 50.0.1, cffi 2.1.1, pycparser 3.0,
  typing-extensions 4.16.0, annotated-types 0.8.0,
  typing-inspection 0.4.4. Todos explícitos, sem resolução transitiva implícita,
  instalação de sdist, build nativo ou execução de dependência no host.
- Preparar árvore `--target` separada com pip `--isolated --no-cache-dir`,
  offline `--no-index --no-deps --require-hashes --only-binary=:all:`,
  sem compile e com alvos de wheel Linux explícitos. Não importar os binários
  Linux no Windows. Gerar inventário/hashes/versões/bytes da árvore; rejeitar
  .pth, links, colisões case-insensitive e nomes que escapem. RECORDs
  conferidos; launchers normais só se declarados por entrypoints, nunca
  invocados. Não executar scripts de instalação.
- Download somente de URLs HTTPS `files.pythonhosted.org` presentes nos
  metadados HTTPS do PyPI, sem resolver/configuração do pip ou proxy com
  credenciais; sem redirect de origem. Confere SHA-256 enquanto baixa.
  Soma comprimida <=100 MiB conferida nos metadados **antes** do download.
  ZIPs só revelam tamanho descomprimido depois: conferir soma declarada
  <=240 MiB antes de instalar, com margem de 10 MiB para metadados/launchers;
  cap de árvore instalada 250 MiB também conferido depois. Não afirmar que
  tamanho instalado foi conhecido nos metadados PyPI. Sem mudar pins do projeto.
- É instalação **parcial de laboratório**: falta deliberadamente MCP/HTTP,
  logo não reivindica pip-check nem instalação operacional completa. Pacotes
  realmente importados e suas origens/versões devem ser conferidos; check
  offline de Requires-Dist com markers Linux/cp311, extras vazios; exceção
  só para mcp/fastapi/uvicorn/scramp/asn1crypto do maskgw. Confirmar
  psycopg.pq.__impl__=binary, e extensões pglast/pydantic_core/cryptography/
  yaml carregadas de `/installed`. Tags só x86_64/cp311 ou abi3 compatíveis
  com glibc da imagem, ou pure Python. Falha
  por dependência ausente é falha da montagem, não evidência de contenção.
- Runtime isolado `python -I -B -S`: uma árvore instalada própria RO em
  `/installed`, adicionada explicitamente ao caminho só pelo harness; módulos
  maskgw/dependências precisam vir dela, não do host. Outro mount RO contém
  apenas os dois scripts do harness (suporte anterior congelado e probe novo).
  Também um JSON de ownership/versões gerado dos wheels verificados, sem
  código ou secrets, com hash conferido antes/depois. Módulos sem __file__
  gerados por PyO3 são atribuídos ao ancestral .so efetivamente carregado.
  Nomes Cython sem arquivo só entram se encontrados nos símbolos dos .so
  já verificados e o caminho exato da extensão estiver carregado. Registrar
  explicitamente generated-by, não inventar __file__ nem prova independente
  de autoria. Módulos file-backed não-stdlib precisam vir de /installed;
  os próprios scripts do harness são exceções fechadas em /probe.
  Nenhum mount gravável, cache, Docker socket ou fonte do checkout.

## Envelope e lifecycle

Um container por caso, no máximo PID1 e um membro. Perfil externo igual ao
anterior: 192 MiB, swap zero, CPU1, pids16, shm1 MiB, nofile64, core0,
UID65534, readonly root, rede none/IPC e cgroupns privados, cap-dropALL,
no-new-privileges, sem init/shell/healthcheck/restart, log driver none.
**Não** saturar o domínio externo nem adicionar pressão de payload.
Prazo de 30 s/caso e 120 s/lote; watchdog independente no host, resposta
até64 KiB/caso e até1 MiB/lote. Reutilizar bounded CLI, save durável,
identidade/cleanup e watchdog do observador revisado, sem modificar os
artefatos ou comportamento do experimento anterior.
Novo observador com perfil próprio de dois mounts/command; reutilização só
dos helpers congelados, não da case()/run() de quatro casos. Supervisor não
importa produto. Conferir glibc no container e compatibilidade com tags
selecionadas, e todo módulo não-stdlib vindo de `/installed`. Variáveis
do container só da imagem, sem `-e`; registrar nomes, não valores.

Orçamento do relatório antes da rodada: baseline de módulos separado dos
deltas, sem segunda lista duplicada de nomes. Inventário completo até1.500
linhas e1MiB descomprimido, zlib<=32KiB/base64, decoder com teto incremental
e sem cauda/frames extras. Probe JSON<=56KiB, wrapper<=64KiB; metadados
até8KiB. Teste com1.500 módulos estruturados longos cabe; entradas de alta
entropia que não couberem viram inconclusivas, sem truncar prova ou aumentar
teto. Nomes/conjunto são derivados do inventário pelo host. É codec só do
laboratório, não alteração do protocolo de resultado D-113.
Prazo interno20s, deixando margem ao deadline externo30s. Interface
/proc/*/children, se ausente no kernel, é registrada como indisponível;
inventário global /proc+cgroup permanece obrigatório. Efeitos de imports são
amostras por etapa, não prova de ausência de efeitos transitórios.

Persistir intenção/nome/hash e ID antes de inspect/start. Inspecionar
limites e exatamente dois mounts RO antes de iniciar. Divergência do perfil
não impede remover o próprio ID confirmado; identidade alheia nunca é alvo.
Confirmar kernel/cgroup efetivo dentro, inventário de processos/threads,
encerrar/recolher membro e remover container próprio. Incerteza de cleanup
para o lote, sem liberar capacidade ou prosseguir. Registrar OOMKilled,
events e limites sem deduzir causa de sinal isolado. Nenhum docker exec.

Preflights somente `docker version`, `ps -aq --no-trunc` e `image inspect`,
com captura limitada e 5 s/call. Não iniciar se outro uso aparecer. Desktop
existente pode ser iniciado oculto e restaurado se inicialmente desligado;
sem mudar daemon, WSL, Python do sistema ou .venv. Preparação de wheelhouse
não executa carga nem exige Docker. Respeitar permissões da ferramenta.

## Revisão/gates e lacunas

Claude2 revisa plano e harness/testes antes de qualquer import real Linux.
Testes puros cobrem ordem, limites/origem, relatório e falhas de lifecycle;
adversarial real de kill/SO continua prova posterior, não inventada aqui.
Fontes antigas e produto devem permanecer idênticos; Ruff/mypy/testes do
lote e auditoria de hashes. Evidência deve preservar tentativas reprovadas,
casos não executados e distinguir coletado vs aprovado.

Não há SQL (nem sintética), banco/DNS, secrets, cursor, worker integrado,
listener, nova dependência/setting ou ponte com registry/leases. Não mede
TLS/arenas sob carga, resultado/AST ou custo global do pai. memory.max não
é exercitado e pode ter excessos transitórios; VM/daemon e orçamento de
produção estão fora. B-1 fim a fim, B-2 e D-090 gate 2 permanecem abertos.
Se os imports não couberem em AS32, o próximo desenho deve usar o custo
medido e margem explícita/orçamento global, não alterar esta evidência.

## Revisão do plano

Primeira leitura do Claude2: seis bloqueadores I1–I6 (efeitos transitivos,
origem/hash, completude, sys.path, árvore Windows e sinais nativos). Os
contratos acima respondem a eles. Duas alternativas explícitas para releitura:
download direto dos URLs/hashes oficiais em vez do resolver pip; tamanho
instalado verificado nos headers ZIP antes de instalar, pois os metadados
PyPI não declaram essa medida. Nada baixado/executado nesta preparação.
Esse parágrafo descreve a revisão inicial, antes da preparação efetiva.
Depois dela, 12 wheels e o produto foram instalados em árvore externa
verificada (656 arquivos/73.346.126 bytes), sem import de código Linux.
Código do preparador foi revisado e P1 de placement corrigido antes da ação.
O harness de imports foi revisado antes da rodada: R1/baseline e R2/orçamento
do relatório corrigidos, 110 testes relacionados aprovados. Claude2 corrigiu
sua afirmação anterior: exec_module não registra _lab_support automaticamente.
Rerevisão sem bloqueador para uma rodada estreita; não é aprovação de B-2.
Referências primárias: [PyPI JSON](https://docs.pypi.org/api/json/),
[pip download](https://pip.pypa.io/en/stable/cli/pip_download/) e
[pip install](https://pip.pypa.io/en/stable/cli/pip_install/).
