# Etapa 8 — diagnóstico sintético Linux AS, não contenção de produção

**2026-10-20 — quatro casos executados uma vez, cleanup confirmado;
registro conferido pelo Claude2 sem bloqueador no escopo do diagnóstico.** O plano é
`PHASE-9-STAGE-8-CONTAINMENT-NEXT.md`. Este lote não
altera produto, plataforma certificada, dependências ou configuração
operacional; não implementa worker nem libera SQL.

## Pergunta e critério predeclarado

O diagnóstico Windows anterior falhou em conter mapeamento compartilhado
de 40 MiB sob limite privado de 32 MiB. Esse resultado permanece válido.
Aqui se pergunta apenas se RLIMIT_AS de 32 MiB, herdado antes do spawn,
recusa expansão privada e MAP_SHARED anônimo nesse interpretador Linux.
Espaço virtual não equivale a RAM nem commit privado Windows.

Quatro casos, uma rodada: baseline de 1 MiB sob AS; controle sem AS com
40 MiB privados e 40 MiB compartilhados coexistentes; dois membros privados
sob AS; dois membros compartilhados sob AS. Passos de 4 MiB até recusa,
máximo 40 MiB/membro, mantendo e tocando todas as páginas até a amostra.
MemoryError/ENOMEM na alocação e VmPeak<=32 MiB são condições separadas;
falha de coleta, outro errno, sinal ou deadline nunca aprovam imposição.
Sucesso exige quatro resultados esperados, fontes estáveis, cleanup e
inventário restaurado; código de saída zero isoladamente não basta.

O supervisor aplica AS a si antes de criar membros; startup anterior só
pertence ao domínio externo. VmSize inicial deve caber em 28 MiB, sem
elevar AS até verde. O container externo nasce com 192 MiB e swap zero,
CPU=1, pids=16, UID 65534, caps removidas, no-new-privileges, rede none,
filesystem read-only e um único arquivo RO. Há watchdog independente no
host, prazo de 30 s/caso e 180 s/lote, saída limitada e limpeza só por ID
próprio conferido. Nada usa banco, payload real, secrets ou Docker socket
dentro do container.

## Preparação medida no host

- Host Windows, `.venv` existente Python 3.11.3; não recriada ou alterada.
- 42 testes puros iniciais dos dois novos módulos: aprovados, sem carga Linux,
  subprocessos reais ou daemon Docker.
- Primeiro mypy apontou 28 erros nos helpers novos dos testes; corrigidas
  apenas anotações. Repetição: mypy strict limpo em 245 arquivos, alvos
  3.11 e 3.14. Não é execução do runtime 3.14.
- Ruff check e format em `src tests`: aprovados (245 arquivos). Os dois
  scripts de PoC passaram format e regras E/F/I/B/UP; não pertencem ao
  pacote nem ao lint padrão de produto.
- RAM livre 15.295 MiB e disco livre 15,01 GiB; Docker/Python sem processos
  antes do diagnóstico. A primeira consulta CIM restrita deu acesso negado;
  valores foram medidos na consulta somente leitura permitida, não inferidos
  dos zeros daquela tentativa.
- Metadados públicos da imagem oficial `library/python`, Linux amd64:
  `python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590`,
  Python 3.11.17, camadas comprimidas 49.907.229 bytes. Consulta ao registry
  não é download nem execução. Tamanho descomprimido ainda não medido.

## Revisão e execução

Claude2, sessão somente leitura `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
revisa `docs/poc/linux_as_probe.py`, `docs/poc/run_linux_as_probe.py` e os
dois testes antes de qualquer caso real. Não há segundo escritor. A primeira
revisão bloqueou a execução por recusa inicial sem bloco retido e falta de
registro durável/limpeza de container próprio com perfil divergente. Ambos
foram corrigidos, junto dos reforços de protocolo e hashes, com regressões;
46 testes puros passaram. A releitura não apontou bloqueador de segurança
restante, condicionada a declarar exatamente os preflights de CLI. Foram
fixados no plano `version`, `ps -aq --no-trunc` e `image inspect` (captura
limitada e 5 s/chamada), sem probes reais extras de subprocesso. Claude2
não executou nada. Esse parecer só permite o diagnóstico de quatro casos,
não aprova B-2 ou produção. Nenhum limite de cota foi observado.

Desktop já instalado iniciado oculto, sem mudar daemon/WSL. Preflight real
limitado confirmou Docker Engine 29.7.2, Linux, zero containers e imagem
pinada ainda ausente. Download só do digest declarado: exit 0, 781 bytes de
saída capturados; imagem local Linux amd64/Python 3.11.17, sem volumes
declarados, ID e RepoDigest iguais ao digest acima. `docker image inspect`
reportou Size=49.914.479 bytes; não é medição de uso físico incremental do
disco nem afirmação de tamanho descomprimido.

## Rodada única medida

Executado pelo Python 3.11.3 nativo do host:

```powershell
.venv\Scripts\python.exe -I -B docs\poc\run_linux_as_probe.py --run <docker.exe absoluto> python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590
```

Interpretador dentro dos quatro containers: Python 3.11.17, kernel
`6.18.54.1-microsoft-standard-WSL2`. Elapsed do observador: 5,984 s,
exit 0, quatro casos completos, nenhum não executado ou repetido,
`diagnostic_success=true` e **`total_memory_contained=false`**. Nenhum
deadline excedido; watchdog fechado; hashes originais e cópias iguais,
conferidos pelo observador/executor, não calculados pelo revisor.

| Caso | Payload retido por membro | VmPeak por membro (bytes) | Recusa / resultado | Tempo (s) |
|---|---|---|---|---|
| baseline sob AS | 1.048.576 | 18.223.104 | sem recusa; normal | 1,484 |
| controle sem AS | membro privado: 41.943.040; membro shared: 41.943.040 | 59.154.432 / 59.113.472 | sem recusa; control_ok | 1,500 |
| dois privados sob AS | 12.582.912 / 12.582.912 | 29.765.632 / 29.765.632 | MemoryError no próximo bloco; imposed | 1,375 |
| dois shared sob AS | 12.582.912 / 12.582.912 | 29.753.344 / 29.753.344 | ENOMEM (12) no próximo bloco; imposed | 1,313 |

Cada membro de pressão reteve três blocos de 4 MiB e tocou 3.072 páginas;
a quarta tentativa de 4 MiB foi recusada. Limite soft=hard conferido em
cada membro: 33.554.432 bytes. No controle ambos tinham AS ilimitado, mas
continuavam sob domínio externo finito. Todos eram de uma thread.

Supervisor iniciou com VmSize=19.660.800, VmPeak=19.775.488 (antes de AS),
abaixo dos 28 MiB predeclarados. Após configurar AS, o valor efetivo foi
conferido antes do spawn. Inventário no platô: PID1 e um membro no baseline;
PID1 e dois membros nos demais; depois do reap, só PID1/pids.current=1.
No controle coexistiram 80 MiB sintéticos, com shmem=file=41.943.040;
esses contadores não foram somados como classes disjuntas.

Picos cgroup: baseline 21.458.944; controle 112.926.720; privado 54.439.936;
shared 53.657.600 bytes. Events max/oom/oom_kill permaneceram zero,
`State.OOMKilled=false`; **o limite externo de 201.326.592 bytes não foi
exercitado**. Não há inferência de que cgroup impediria todo excesso.
O resultado estreito mostra a recusa de bytearrays e mapeamentos anônimos
MAP_SHARED, em passos de 4 MiB, nesta rodada única/kernel/imagem. Não é
comparação de cotas equivalentes com o diagnóstico privado Windows.

## Artefatos, cleanup e proveniência

Diretório próprio preservado fora do checkout:
`%LOCALAPPDATA%\Temp\maskgw-linux-as-20261020-dh8e9s_m`.
Oito arquivos, 55.416 bytes totais (dois scripts, quatro casos, pending e
sumário), cada relatório abaixo de 64 KiB e total abaixo de 1 MiB.
O alias 8.3 retornado pelo host aponta para o mesmo diretório.

- SHA-256 do probe executado:
  `8170a37b892bd6d2bdae351bacd05f0e047d8bbc9b2b54bad695da7419380e0b`.
- SHA-256 do observador executado:
  `58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627`.
- SHA-256 de `summary.json`:
  `925a248e52f4ae383b9154742a765a1a3fb5b402252c077cee56cf0de6ee6155`.

Cada caso guarda seu ID exato. `pending.json` durável registra primeiro a
intenção, depois o ID antes do inspect/start; é sobrescrito pelo próximo
caso, mas os IDs persistem nos quatro relatórios. Falha ao gravar a fase
removed torna o lote inconclusivo mesmo se a remoção já ocorreu: comportamento
fail-closed, não recibo fictício de cleanup.

Todos os containers próprios foram removidos pelo ID conferido; inventário
do engine vazio antes/depois, confirmado novamente antes de parar o Desktop.
Desktop stop graciosamente, exit 0; observação posterior: zero processos
Docker Desktop/backend/build e zero Python. Imagem baixada permanece no cache;
artefatos de evidência foram mantidos. Nenhum banco, container existente ou
arquivo pessoal foi tocado. Sem teste de timeout/kill real injetado nesta
rodada; caminhos adversariais do observador têm testes com fakes, não prova
de falha real do SO/daemon.

Claude2 conferiu a coerência do registro com o código, mas seu Read do
diretório temporário foi negado mesmo com add-dir; não se atribui leitura
daqueles originais nem cálculo de hash ao revisor. Uma cópia legível do
sumário sintético (com os quatro casos embutidos), em
`docs/poc/evidence/linux-as-20261020-summary.json`, foi preparada para
conferência no escopo normal do checkout, sem ampliar permissões ou mudar
os originais. Ela não contém produto, dados de banco ou secrets. Não é um
novo experimento nem substitui os hashes dos originais acima.

Na conferência final da mesma sessão, Claude2 leu essa cópia no checkout e
não encontrou divergência/bloqueador no registro. Conferiu valores dos quatro
casos, ambiente, limites, inventários e cgroups, sem calcular hashes nem
certificar cleanup por execução própria. A cópia possui um LF final a mais;
executor comprovou igualdade de bytes após strip e igualdade de JSON com o
original. SHA-256 próprio da cópia:
`c82eaa4050de02599cb01fd196c5f9c721e33fec93adf540fe898ea00656aee5`.
As quatro entradas embutidas foram comparadas pelo executor aos relatórios
separados. Nenhuma alegação de revisão dos originais negados é feita.

Produto e dependências não mudaram. A suíte integral PG16 de 6.395 passed
é histórica da D-115, não foi reexecutada/reivindicada neste lote. Não foram
repetidos frontend/browsers/pacotes nem runtime moderno: o trabalho novo é
somente harness isolado, dois módulos de testes e documentação. 46 novos
testes puros, Ruff/format e mypy nos dois alvos são os gates deste incremento.

Checkpoint Git permaneceu `4a5e5560abb495898c9e1b8ca44ac2d155681015`,
com referência local origin/master `5d173ea938eb12db33bc880bf67a2e81a208fd5e`,
1 ahead/0 behind (sem fetch). Permissão efetiva de `.git` continua somente
leitura: nenhum commit/push tentado. Auditoria do lote: oito documentos
anteriores atualizados e seis arquivos novos (dois scripts, dois testes,
esta evidência e cópia sintética do sumário); código de produção e lotes
anteriores preservados, nenhum arquivo selecionado ausente. `.venv` e
artefatos pessoais não foram alterados por este lote.

## Limitações que não desaparecem

Os 192 MiB externos não são saturados por estes casos: imposição efetiva de
memory.max não exercitada. Tmpfs por write, cache, kernel, sockets/pipes,
VM/containerd/dockerd e custos do pai ficam fora desta prova. Cgroup pode
ter excessos transitórios; shmem já integra file. MAP_SHARED anônimo não é
limitado pelo mount `/dev/shm` de 1 MiB. Imports do worker real, TLS, arenas,
threads, orçamento global e cleanup do pipeline integrado não são medidos.

B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos. Nenhuma liberação de
produção ou certificação Linux/Windows de SQL resulta deste diagnóstico.
