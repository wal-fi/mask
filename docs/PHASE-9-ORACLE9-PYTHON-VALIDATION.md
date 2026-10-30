# Oracle9 — evidência da preparação Python

## Primeira tentativa, consumida e reprovada

2026-10-23. Procedimento v3 revisto antes da ação, root2cb63b66,
task1405edda0f844b4e8a5a5ae170c116c1. A iniciou Desktop próprio, nove
observações reais/Ready passaram. B executado exatamente uma vez, exit2.

`install-runtime` terminou exit1 em2,766s. Log público interno de485bytes
registrou BASELINE e INSTALL, seguido de:
`error: (--setopt) Unable to handle: gpgcheck=1`.
Assim a flag global não é aceita pelo microdnf desta base. Não atribuir
essa falha a caps, GPG inválido, rede ou memória. A instalação não passou;
nenhum commit de imagem ou segunda sonda aconteceu. Não há runtime pronto.

Perfil inspecionado antes de start; container próprio removido por CID;
inventário global vazio. AllowStop/restore/Off exit0. Ausência de processos
Docker observada23:25:36.7645308Z, sem claim de VM/WSL desligado. Nenhum
prune, mudança de host, segredo, DB ou produto executado.

Registro imutável `docs/poc/evidence/oracle9-python-attempt1-20261023.json`,
7.464bytes, SHA256
`1d4b08c2875a5e3ba16909274d2eaced5f987cd2b3946ace690af5567274a22d`.
Fontes v3 preservadas no JSON citado pelo registro; não repetir o attempt.
Os44 testes puros e a revisão pré-ação não eram prova de compatibilidade
do CLI Linux. Nenhum gate B-1/B-2/D-090 foi fechado.

Uma nova tentativa corrigida requer fonte/pins/roteiro novos e revisão
antes de ação, preservando este NOT_PASSED e seus exits.

## Segunda tentativa, consumida e reprovada

Procedimento v4 aceito na revisão71790, rootbb4fc0ab/taskfb1112bd.
Flags GPG/TLS nos repos mantidas; retirada só das flags CLI incompatíveis.
A, nove observações e Ready passaram; B uma vez, exit2. Install exit137
em62,516s; log486bytes terminou nos dois `Downloading metadata...`.
Nenhum commit ou sonda de imagem. Container removido/inventário vazio.

Diagnóstico **separado, somente leitura, fora dos comandos do roteiro
original**, depois da falha e antes de restore: events filtrado somente
pelo CID próprio removido, desde o start, e info MemTotal. Ambos exit0.
Eventos create/attach/start/**oom**/die137/destroy confirmados para esse CID.
Não há amostra de pico ou distribuição RSS/cache, nem prova de qual repo
causou o consumo. Observer v4 não persistiu State.OOMKilled, só o hash do
inspect no cleanup; não inventar esse campo retrospectivamente.
MemTotal16.689.958.912 bytes é total do daemon, não memória livre.

Restore25515 e Off exit0, ausência de processos23:34:46.9492383Z. Nenhum
prune ou mudança no Windows/WSL/configuração do Docker. Registro imutável:
`docs/poc/evidence/oracle9-python-attempt2-20261023.json`,11.519bytes,
SHA256 `a580fe9bef6ed8ea293911d045b9cba8466bcf621fcddf3c61cfb93044a79576`.
NOT_PASSED permanece. Não é teste de pressão ou evidência de B-2.

Decisão técnica sob delegação para nova preparação: perfil separado2GiB
só para o gerenciador de pacotes públicos, com revisão antes de ação e
raiz/pins novos. Não é aumento automático durante a rodada nem alteração
do perfil de128MiB da sonda ou aceite operacional D-119. Nenhuma imagem
foi produzida nas duas rodadas; gateway ainda indisponível.

## Terceira tentativa, consumida e reprovada

V5 aceita87482; rootc66036a7/taskb4302d50. A, nove observações e Ready
passaram. B uma vez/exit2, instalação exit1 em69,953s. Pré-condição
MemTotal16.689.967.104 passou. Log2179bytes resolveu nove RPMs novos,
nenhum upgrade/remove/downgrade e transaction test seguido de instalação,
mas terminou `error: Error -1 running transaction`. Causa específica
desconhecida: não declarar falha de capability como comprovada.

Inspect próprio persistido antes de cleanup: Runningfalse/ExitCode1/
OOMKilledfalse. Sem commit/sonda; CID próprio removido e ps vazio. Restore
87410/Off exit0; ausência23:43:56.1923347Z. Nenhum diagnóstico extra/carga,
mudança de cota em execução ou configuração do host.

Registro imutável `docs/poc/evidence/oracle9-python-attempt3-20261023.json`,
com os originais e fonte v5. Próximo desenho deve obter diagnóstico mais
específico sem desligar assinaturas ou inventar sucesso. A lista resolvida
dos nove pacotes permite preparar bundle fechado e teste RPM offline,
evitando metadados mutáveis e rede no instalador. É novo procedimento,
dependente de revisão antes de downloads/ação, não replay da v5.

## Quarta tentativa (offline), consumida e reprovada

V7 aceita62356, root499ec65a/task2fb1281f. D baixou uma vez e A/nove
observações/Ready passaram. B uma vez/exit2; instalação/atestação exit1
em8,860s, OOMKilledfalse. Input13 normalizado0:0/644 e hashes conferidos;
nove signatures OK/keyID permitido, headers/modos/caps declarados e
dependency test passaram. RPM instalou os nove; venv foi criada; o Python
do atestador confirmou3.11.13 e chegou à verificação dos pacotes antigos.

O wrapper recusou stderr não vazio ou rc fora0/1 de `rpm -V nome.arquitetura`.
O stderr original não foi retido, portanto a causa específica ainda não é
comprovada. Nenhum commit ou sonda final. Não chamar a imagem pronta.
Novo mecanismo+caps não provam a causa do erro-1 da terceira tentativa.
Cleanup próprio/ps vazio; restore27429/Off exit0, ausência de processos
2026-10-24T00:18:05.2949866Z (ainda23/10 no fuso local).

Artefato imutável `docs/poc/evidence/oracle9-python-attempt4-20261023.json`,
15.227bytes, SHA256
`01c6665c68021fd7dd165abb797913a5bef3abf06eb0857917f85188c58adeb9`.
Próximo lote deve preservar a recusa, melhorar a consulta/diagnóstico e
reutilizar apenas bytes de RPM conferidos em **nova** tentativa, sem novo
download nem replay de A/B/D consumidos. Bundle original intacto.

## Quinta tentativa (v9), consumida e reprovada

V9 aceita94432, root963040fd/task94d91ee3. A/nove observações/Ready
passaram. B uma vez/exit2, install/atestação exit1 em10s, OOMKilledfalse.
RPMs/venv passaram. Dessa vez `rpm -Va` retornou rc aceito/sem stderr,
mas a saída normalizada diferiu da baseline. Não houve diagnóstico das
linhas diferentes; sem causa atribuída ou exceção nova autorizada.
Nenhum commit/sonda, cleanup/ps vazio, restore35708/Off exit0, ausência
2026-10-24T00:37:58.3893012Z. D não repetido, RPMs originais intactos.

Registro imutável `docs/poc/evidence/oracle9-python-attempt5-20261023.json`,
11.727bytes, SHA256
`b871d42bea73616fcc3505afca25e702244ad51bb133c594882fe059d8f4abf8`.
Próxima rodada só acrescentará diagnóstico público limitado dessa diferença,
sem afrouxar a igualdade, para identificar a correção efetivamente necessária.


## Rodadas diagnósticas adicionais preservadas

6 (v10,90167519) NOT_PASSED: nenhuma linha de verificação adicionada;
somente três missing de diretórios removidos, sem prova de modo/owner.
Artefato attempt6-20261023, SHA6bacfcb352c688f3ef09362b2644ec4c30eb0e00d3b3a9c9a3eacb7554d8fc55.
Cleanup/Off2026-10-24T00:52:11.2890650Z. Não é PASS retroativo da policy nova.

7 (v12,f683aa16) NOT_PASSED, outer2/install1/9,750s, sem OOM. Assinaturas,
instalação dos nove RPMs e venv passaram; aux-cache com owner glibc|x86_64
medido. Payload recusou em require(owner is not None) do inventário novo,
sem registrar o caminho. Não inferir qual arquivo nem ampliar regra.
Nenhuma imagem commitada. Cleanup próprio e ps vazio; restore0/Offtrue
2026-10-25T22:38:56.1291072Z. Artefato imutável:
`docs/poc/evidence/oracle9-python-attempt7-20261025.json` (12.017 bytes),
SHA91d300f23ecfa2899d6c69ec77b66345656f9b923e3fe555b006c5d7c6bd7eb9.
A e seis observações ocorreram no dia24 UTC; após pausa do usuário, as
três finais e B/C no dia25. PID/start-time da aplicação permaneceu igual,
B conferiu pins e inventário. São90s de espera comandada, não90s contínuos
nem prova de disponibilidade durante a pausa. O protocolo não tinha teto
entre observações. Histórico preservado; não ocultar o intervalo.


8 (v13,6bdaacb4) NOT_PASSED: diagnóstico completo dos três paths em
LIB64-ATTESTATION-PLAN; artefato attempt8-20261025 de12.865bytes, SHA
56bf111fd97cab72c92212e50c2dc513c0c0de4f0f2443e68de3882df7c9ad7c.
Sem OOM/commit; cleanup e Offtrue2026-10-25T22:45:25.5493398Z.

9 (v14,52d3b130) NOT_PASSED em parsing do stdout de commit. Arquivos,
RPMs, alias/inode/conteúdo/cache/diff passaram; install0/10,093s. 4.035
paths novos e5.938 nós conferidos para privilégios; runtime.json912.858
bytes, SHAd3a2747167423282a8e361e18d01e7ab48ed6df996225ec5b634e7d05fc4c616.
Alias antes/depois iguais e dois nós com dev/ino idênticos nos dois paths;
diretório alvo /usr/lib64 modo0555. Cache antes ausente, depois regular
root0644,6.383bytes e ownerglibc. stdout de commit teve179bytes e exit0,
mas texto original não foi salvo; causa/formato não atribuídos.
Imagem criada permaneceu em quarentena, sem sonda final ou reutilização.
Diagnóstico próprio extra, **fora de B**, só image-inspect: imagem ID
sha256:23b754ea395c84d24579051e653e8bd79d9e2c1843853a216a7f88392cd4b48a,
metadados preservados em attempt9-image-diagnostic-20261025, SHA
54080d90449882abdf18e3a2bea37560dd27399ea0a825f1545ba8ab3314fa04.
Não é atestação de disponibilidade. Cleanup/ps vazio, restore0 e
Offtrue2026-10-25T23:01:17.1873447Z. Desvio de sequência C: host futuro
foi editado depois de B e restore terminais0, antes de Off; Off conferiu
somente os scripts próprios inalterados por hash. Não houve mutação de
fonte durante B; não alegar wrapper integral original passado em Off.


## Resultado final medido — rodada 10 (v15), 2026-10-25

**PYTHON_RUNTIME_PASSED/outer0**, somente imagem intermediária do Python.
Raiz6c872481/task4f1d385b3e18464792773488386438dd; fontes/pins v15,
pré-revisão71780 sem bloqueador. A/Observe3/Ready/B/C separados, todos
terminais0, fontes inalteradas e pins completos até Off. Sem D/rede no
builder/RPM novo ou mudança de caps/limites. Nove NOT_PASSED preservados.

- Imagem ID `sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4`,
  tag local `maskgw-oracle9-python:4f1d385b3e18464792773488386438dd`.
- 24 comandos CLI com exit0; install10,406s; final probe0,594s. Sem OOM.
- Oracle9.8/Python3.11.13, OpenSSL3.5.8 e SQLite3.34.1. UID/GID10001;
  probe networknone/read-only/capdropALL/128MiB, swap0/pids16/fds64,
  NNP/core0; isso não prova dumpable0 antes de segredos ou domínio total.
- 4.035 paths novos e5.938 nós na varredura de privilégios. Alias antes/
  depois idênticos; dois nomes libtirpc representam os mesmos dev/ino;
  arquivo SHA igual ao header assinado, query canônica RPM vazia. Cache
  regular root0644/6.383bytes, antes ausente, dono glibc anterior inalterado.
- Base RPM aceita com restauração dos três diretórios documentados;
  **base_verify_unchanged=false**, não afirmar igualdade total da baseline.
- runtime.json912.858bytes, SHA
  `e9b652d7ec7bd1d1f030ecb09e75b4601e80e6753dd4e93eec5d45d8eb995db7`,
  mesmo hash retornado pela sonda; relatório revalidado no host após Off.
- stdout de commit salvo179bytes: aviso de depreciação de --pause e ID.
  É fato desta rodada, compatível com a falha anterior; texto antigo não
  foi retido e não se reconstrói retroativamente sua causa exata. CLI
  docs: https://docs.docker.com/reference/cli/docker/container/commit/ e
  https://docs.docker.com/reference/cli/docker/image/inspect/ .
- Dois containers próprios removidos e ps vazio; restore0/Offtrue
  `2026-10-25T23:07:58.6258954Z`. Imagem final cacheada, não em execução;
  imagem da tentativa9 em quarentena. Nenhum banco existente tocado.

Artefato completo `docs/poc/evidence/oracle9-python-attempt10-20261025.json`,
876.824bytes, SHA057bff0522d6297f408e627793c180eada11fbbb0cf4cfe0e03be03520b3e583.
Resumo verificável `oracle9-python-runtime-summary-20261025.json`,12.212bytes,
SHA2ee2f0c7a83107c6fd80659841cac89290c188055b1f86df6e7d265c418cb1b1.
Cópias UTF8 originais preservam inteiros/bytes; não passar timestamps ou
inodes por JSON Number de JavaScript. JSON inspect da imagem final não
foi guardado bruto: só hash/tamanho/exit e validação obrigatória pinada.
Não alegar rerevisão independente dos bytes integrais desse inspect.

154 testes puros/fake-stat direcionados, Ruff/mypy dos quatro testes e
format de sete arquivos passaram. Scripts sem certificado de lint completo
(histórico143avisos); E9/F63/F7/F82 passaram antes da última extração do
validador de imagem. Suíte de produto/Node/browsers não repetida: nenhum
produto/src/dep/UI mudou neste lote. Quatro pins D-118/guards conferidos
intactos. Próximo: revisão desta evidência e fechamento de dependências
**no alvo Linux**. Não derivar lock final de freeze Windows. Sem app,
worker integrado, consulta SQL, B-1/B-2/D-090 fechado, commit/push ou
Gateway disponível. Variações de inodes/timestamps/runtime.json impedem
prometer dois builds bit-idênticos; digest/inputs exatos identificam esta imagem.

Revisão final 79449 terminou sem bloqueador para usar **este ID** como
base da preparação de dependências, sem declarar Gateway pronto. Próximo
preflight deve guardar inspect bruto e as duas DiffIDs; falta da imagem
bloqueia, nunca substituição silenciosa. Novo perfil/lock Linux e decisão
sobre artefatos públicos e pip da imagem final devem ter revisão própria.
Não usar imagem em quarentena, nem herdar --pause depreciado em código novo.
