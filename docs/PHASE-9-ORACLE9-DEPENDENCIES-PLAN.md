# Oracle9 — fechamento de dependências no alvo Linux

Escolha técnica sob delegação, não aprovação individual nova. Base Python
intermediária validada e revisão final79449 sem bloqueador para usar este
ID local: `sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4`.
Fonte em PYTHON-VALIDATION/summary2ee2f0c7. Não usar tag nem imagem em
quarentena23b754ea. Se faltar, bloquear e preparar nova imagem sob revisão;
não pull/substituição silenciosa. Nenhum Docker ativo agora.

## Próximo incremento: somente relatório de resolução

Objetivo: obter resolução real Linux/CPython3.11.13, com versões/URLs/hashes
exatos e markers avaliados no alvo. Não instalar a aplicação ou novos
pacotes, construir wheel, abrir DB/SQL/MCP/UI/worker, nem usar credenciais.
Os pins diretos de deploy/constraints-tested.txt são semente das versões
já medidas, não lock Linux. A lista completa de requirements vem de
pyproject.toml e seu hash; não usar freeze Windows. Wheel próprio entrará
na instalação offline futura depois de build fora do checkout validado.

1. Novo host/payload de preparação isolados (fora de src) e testes puros,
revisão/pins/raiz nova e roteiro antes de ação. Não reutilizar attempts.
Preflight do Desktop/contexto e inventário, imagem somente por ID fixo.
Guardar inspect bruto dessa imagem **antes** de criar container; validar
linux/amd64, ID/configuração/task/runtimes da origem e baseDiffID+uma
camada, gravando segunda DiffID. Guardar info/versão e capacidades reais.
2. Resolver em um container próprio: USER10001:10001, rootfs read-only,
cap-drop ALL, NNP, sem bind/volume/socket/ports/privileged, namespaces
privados, core0, fds128, pids32, CPU1,512MiB/swap0/shm1MiB; tmpfs /tmp
com128MiB/nosuid/nodev/noexec/uidgid10001/modo0700. Sem escrita persistente
fora desse tmpfs. Não é teste de B-2 ou pressão de memória.
3. **Só resolução** usa network bridge com índice HTTPS do PyPI fixado pelo
pip. Não há allowlist de egress; bridge pode alcançar LAN/host. Exposição
aceita sob delegação só para resolução pública sem dados/segredos. Sem
hostnetwork, proxy, login ou configuração/credenciais do host. Nenhum
MASKGW/DSN/PYTHON*/PIP* do host herdado; ambiente reconstruído. Nenhum
segredo de cliente no container. Payload Python público passado por argv
em -I -B -c (teto32KiB); requirements/constraints literais do arquivo
pinado, nunca comandos de shell. HOME da imagem /var/empty, nenhum mount.
4. Pip do próprio venv do fornecedor, sem upgrade nesta rodada. Registrar
versão. --isolated/--no-input/--no-cache-dir/--disable-pip-version-check,
install --dry-run --ignore-installed --report /tmp/own/report.json,
--only-binary=:all:, --index-url https://pypi.org/simple, --retries0 e
timeout15 por acesso. Comprovar ausência de /etc/pip.conf, /etc/xdg/pip/pip.conf e venv/pip.conf,
sem XDG_CONFIG_DIRS no ambiente; recusar se existir qualquer um deles;
jamais ler config do host ou aceitar extra-index. Dependências podem
exigir download temporário para ler metadata, mas nunca execução de
setup.py/build backend, instalação, sdist ou import dos pacotes resolvidos.
5. Prazo do processo pip150s e global do próprio container180s; saída
envelope JSON<=2MiB e diagnóstico público limitado. Bruto pip<=16MiB no
tmpfs, emitir bytes/hash e projeção fechada, mais bruto zlib/base64 com
tetos16MiB raw/2MiB envelope. Host revalida projeção a partir do bruto,
com descompressão limitada/EOF/sem cauda e hash/tamanho exatos. tmpfs128MiB impõe teto de
armazenamento temporário; memória512MiB inclui esse custo. OOM/error/timeout
recusa, cleanup por IDs próprios e sem retry automático. Entradas e fonte
públicas hashadas; antes de pip exigir UID/prefix/python/plataforma esperados.
6. Validar relatório **versão0, pip22.3.1**, hash em archive_info.hash
na forma sha256=<64hex>; sem fallback para versão1/hash ausente. Fonte
primária da versão exata confirmada antes de código, abaixo. Validar: ambiente linux/x86_64/3.11.13, pip da imagem,
lista1..64, nomes/versões únicos e constraints diretos satisfeitos; só URL
HTTPS files.pythonhosted.org sem credencial/query/fragment, filename .whl
ASCII seguro, hashSHA25664hex. Recusar sdist/URL extra/ausente/duplicado/
nome inesperado ou Windows/macOS/musllinux/plain-linux wheel. Só
py3-none-any/py2.py3-none-any ou cp311/abi3 compatível comCPython3.11 e
manylinux x86_64 com glibc<=2.34 (libc medida no alvo). is_direct deve ser
false; nome/version do filename coerentes com metadata. Projeção inclui
requires_python/requires_dist para revisão, sem description/readme.
Registrar bruto comprimido e lista reduzida
imóveis por hash. Relatório não é prova de segurança dos pacotes nem lock
instalado; erros de resolução não autorizam relaxar pins durante a rodada.
7. Cleanup/remove próprio, inventário final e restore Desktop ao estado
inicial, mantendo imagens cacheadas. Fonte congelada de A até Off. Uma
execução A/observações/Ready/B/C revisada, sem pausas longas; interrupção
aborta sem B. Sem cota observada/job/outro escritor. Só depois de revisão
da evidência, desenhar download fechado/limitado por arquivos e hashes,
wheel próprio e instalação offline --require-hashes/--no-index/--only-binary.

Referências primárias: https://pip.pypa.io/en/stable/cli/pip_install/ ,
https://pip.pypa.io/en/stable/reference/installation-report/ e
https://pip.pypa.io/en/stable/topics/secure-installs/ . Comportamento do
pip vendor22.3.1 deverá ser medido; docs atuais não certificam essa versão.

Preparação não fecha B-1 fim a fim/B-2/D-090 gate2 ou C1 e não libera SQL
ou produção. Antes de segredos reais, dumpable0 e resto do domínio completo
continuam obrigatórios. Conteúdo público de atestação e pip da imagem
intermediária serão tratados explicitamente na receita final, sem apagar
recursivamente nada do host. Produto e ambiente Windows permanecem intactos.


## Correções antes de código (revisão3281)

B1/B3/B4 incorporados acima: schema0 específico do pip vendor, bruto16MiB/
envelope2MiB/projeção fechada, e declaração honesta da ausência de filtro
de egress. B2 será resolvido pelo caminho mais restrito: ausência comprovada
dos três configs e XDG_CONFIG_DIRS; nenhum PIP_CONFIG_FILE no ambiente.
Correção factual à premissa da revisão: o **código22.3.1** considera
PIP_CONFIG_FILE mesmo com isolated=True e /dev/null faz _load_config_files
retornar cedo. Não dependemos desse comportamento; usaremos ausência.
Fontes primárias exatas, consultadas antes de implementação:
- https://raw.githubusercontent.com/pypa/pip/22.3.1/src/pip/_internal/models/installation_report.py
- https://raw.githubusercontent.com/pypa/pip/22.3.1/src/pip/_internal/models/direct_url.py
- https://raw.githubusercontent.com/pypa/pip/22.3.1/src/pip/_internal/configuration.py

Entram só [project].dependencies, incluindo o extra binary já declarado em
psycopg[binary]; sem extras opcionais dev/test, sem pacote próprio. Lista
literal/constraints/hash guardados; relatório recusa pywin32/pypiwin32/
pywin32-ctypes, compara cada pin e roots. IndexURL efetivo explícito.
TLS: usar --cert literal /etc/pki/tls/certs/ca-bundle.crt, registrar path
resolvido/hash/tamanho do bundle imutável da base; sem trusted-host/override.
Não declarar impossibilidade global de interceptação se um CA for confiado.
Antes da ação, estimativa dos wheels maiores pelos metadados públicos da
versão pinada será registrada, com lacunas explícitas de transitivos e
backtracking; não aumentar orçamento durante a rodada.


## Código e procedimento v2, antes da ação

Desenho rerevisto por52767 sem bloqueador. Código público novo:
`deploy/oracle9_dependencies.py` (payload/validador puro compartilhado) e
`docs/poc/oracle9_dependencies_resolve.py` (host).62 testes novos/216
relacionados passaram; Ruff e mypy dos dois testes novos passaram;
format dos quatro e E9/F63/F7/F82 dos dois scripts passaram antes do
último campo de daemon-info. Não se alega lint completo de scripts.
O teste inicial existiu antes do módulo (falha por ausência, não finding).

Host exige fontes, entrada e imagem fixas; guarda inspect bruto da base
antes de create, metadata selecionada do daemon (sem campos proxy) e
inspect antes/depois do próprio container. Só CID com task/source/image/
name comprovados entra no watchdog. Cleanup usa identidade independente
do perfil para remover nosso container parado mesmo se um limite falhar.
Nenhum diretório do host é montado, nenhum pacote é instalado.

Tempo: watchdog independente300s do host, CLIattach/container180s, pip150s,
mais recolhimento verificado. Não são promessa absoluta se o SO/daemon
falhar em recolher; nesse caso não declarar cleanup/restore/ready. MemTotal
mínimo2GiB é elegibilidade, não prova de RAM livre. tmpfs128MiB é teto do
armazenamento temporário, incluído no custo de memória512MiB. Sem incremento
de recursos ou retries durante a execução. Native stderr UTF8<=16KiB
preservado integralmente com hash (inclui aviso experimental), stdout
pip<=64KiB; retorno0 e relatório válido exigidos. Código público comprimido
por argv (7.207 caracteres de comando), nenhum input secreto. Validador
host é carregado dos mesmos bytes conferidos. Bruto do pip comprimido com
sha/tamanho/exactEOF, projeção rederivada e comparada antes de aceitar.

Estimativa prévia, não medição do lote: PyPI informa6,3MB para pglast8.4
cp311/manylinux x86_64 e5,2MB para psycopg-binary3.3.4 equivalente, soma
aproximada11,5MB desses dois. Fontes públicas primárias:
https://pypi.org/project/pglast/8.4/#files e
https://pypi.org/project/psycopg-binary/3.3.4/#files . Tamanhos de
cryptography/transitivos não medidos nesta consulta (página cryptography
expirou). Reserva de planejamento conservadora para eles/metadata até64MiB,
não comprovada; somada aos dois fica abaixo128MiB. Backtracking/downloads
inteiros podem ultrapassar: falha recusa, sem aumentar teto na rodada.

v1 preparada não executada, substituída pela v2 que registra daemon-info
selecionado. Nova raiz
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f`,
task417aca720a7e4e809d96ce3ad4b084f2. Estado unobserved/invokedfalse/sem phase.
Cópia de fontes/estado/inputs `docs/poc/evidence/oracle9-dependencies-procedure-v2-20261025.json`,
SHA3c86a44954f56f0deb5bf17ac7eb34299d02b13cb62cc6171b91569ea41ed296.
Pins:
- start7991b3c70b90cdeee58a9a840324e665a556696d38b86a4e432bb381e7160add
- controlf6447bd892ffe873c005e66299da6e415ba6edbeba25f7f35a15758229b22edc
- restoreb27d934e9da8563b75667161259200513b603895e297d938f36d0c41c196ca67
- host55c1eeddc1f01f1b07d33ef3d956441bf0022fe5f59196820c0494c91ff13239
- payloade339fab321e60d8139525b8c2242d1fc255a13b8d66ec18eff3d14e902799cf7
- helperfoundation0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5
- pyproject917fe7353178849ec9e7f53627fc0ce2e0be9fb7678d6dcd2e42f79b925de8f9
- seedfd77310ae3394648acba2883fe2e96cbc398b506a3b980fe8e8047c2695f0e1e

Após revisão do código e roteiro, conferir pins/inputs/estado reais antes
de A. Chamadas separadas, uma vez, sem pausa longa, cada terminal0 antes
da seguinte:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\state_control.ps1' Observe
# Mais duas Observe separadas, depois Ready:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_dependencies_resolve.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f'
exit $LASTEXITCODE
# B terminal/cleanup/ps/ownership comprovados:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-resolve-20261025-81d74d8f\state_control.ps1' Off
```
Sem fonte editada de A até Off. Interrupção longa antes de B aborta sem B;
fora disso qualquer falha não gera retry automático. Cleanup não mata
outros containers nem apaga imagens. Fonte/base/ambiente/procedimento
serão rerevistos se mudarem. Nenhuma ação Docker/rede neste incremento
até a revisão pré-ação, nenhuma dependência/produto/DB/SQL alterado.


## v3 — diagnóstico de falha preservado antes de ação

Revisão22631 não encontrou bloqueador na v2, com recomendação incorporada:
se pip falhar, stdout/stderr são percorridos em blocos, hash/tamanho total
registrados e só prefixo16KiB decodificado com replacement emitido antes
da recusa. Assim stderr grande ou nãoUTF8 não perde diagnóstico. Ramo de
sucesso continua estrito e UTF8 exato. Byte final newline agora incluído
no teto de envelope. Teste novo com100.008bytes e prefixo inválido passou;
63 novos/217 relacionados verdes, Ruff/mypy dos testes novos verdes.
v1/v2 não executadas. Fonte do host55c1eedd permanece igual.

Só a raiz v3 candidata: f74abc9d/task4831a64ee91c4732a57eb502e0afe227.
Cópia `docs/poc/evidence/oracle9-dependencies-procedure-v3-20261025.json`,
SHA248974e3baf4b4682dd1c8eb464740c224b509707f277c2b7d1ba11dd4bf9b66.
Payload011ba3744ab393b1887fcd3290e66d3a507eb9297f1929e39f2e5a03269f2c3a;
start331ed44812e318e917e864de310e33a968b254a5e50fa8b1e19143191b1bba7d;
controlc678e1130ab2474562d6d019e7c7e739e4f477d1df4e4ef9d8cc45ded965e6fa;
restoreb27d934e9da8563b75667161259200513b603895e297d938f36d0c41c196ca67.
Demais pins iguais v2. Comando comprimido7.491caracteres; roteiro igual
substituindo só raiz por f74abc9d, depois de rerevisão curta e pins reais.
Nenhuma ação Docker/PyPI/install ainda neste lote, sem outro escritor.


## v4 — correção do controle antes da reserva de startup

v3 A falhou com exit1/BUNDLE_NOT_READY antes de START_RESERVED, escrita de
estado ou lançamento do Desktop. A cópia do controle RPM ainda exigia
campos de bundle inexistentes no resolvedor; falha nossa de integração do
controle, não de rede ou pip. Zero processos Docker observado depois,
nenhum B/PyPI/install executado. Artefato `oracle9-dependencies-attempt1-start-failure-20261025.json`,
1.430bytes/SHA5196eff9dbe6ff66f16c89d3f1daeb501f5c2d8eb132ac589112fe56f63973c9.
Não reutilizar essa raiz ou inventar campos bundle_ready.

Antes de criar nova raiz, substituir **somente** a precondição RPM pela
conferência do imageID e dos hashes reais de programa/payload/pyproject/
seed, antes da reserva. Estado/lifecycle/allowlist/ownership inalterados.
Python do host/payload/inputs e seus hashes não mudaram. Nova raiz v4:
9ed658f2/taskd8c06b17ed9e4287aff515719d5bcf1a; estado inicial sem phase.
Cópia `docs/poc/evidence/oracle9-dependencies-procedure-v4-20261025.json`,
SHA448508cda42f992d06be84a1135b0986d21ca7a99b98a3fe0d46a9e38efd5efb.
start7793b6c8a36e652f2e14a8149332992afdb3cc6e9c5f8168abef0984e9dcdf1b;
control03417f2195fc363013fbda5ae63659012e20542cfc582d73b4f3c35291748e98;
restoreb27d934e9da8563b75667161259200513b603895e297d938f36d0c41c196ca67.
Demais pins v3 inalterados. Roteiro igual substituindo só raiz por9ed658f2.

Parser AST nativo do PowerShell passou para start/control. O prefixo exato
do start pinado até antes de Add-Member/primeira escrita foi executado
somente como preflight de leitura: guards passaram e hash do attempt.json
antes/depois idêntico, sem reserva/lance/app/env alterado. Não foi uma nova
chamada A. Essa conferência não substitui revisão pré-ação da correção.
A primeira geração de v4 deu erro de parser da expressão JS de geração
antes de executar Python; corrigido e nova raiz criada uma vez, sem efeitos
Docker. Não há novo download/pip/instalação.217 testes anteriores continuam
medidos, não repetidos porque nenhuma fonte Python mudou desde eles.
