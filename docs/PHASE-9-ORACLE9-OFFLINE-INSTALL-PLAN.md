# Oracle9 — imagem candidata com instalação offline (proposta)

Escolha sob delegação, não aprovação individual inventada. Nada executado
por este plano. Entradas aceitas: fundação Python1546afef, resolução Linux,
D/I de36wheels e wheel próprio9181d955/429.231bytes. Objetivo: candidato
de import/recursos. Não serviço, SQL, release ou B-1/B-2/D-090 fechado.

## Preparação host e contexto fechado

Raiz Temp exclusiva:36wheels D8ca7de53 +primeiro wheel próprioad017213.
Revalidar origens/manifestos/I e fonte do projeto conforme resultadod0909fcf
antes/depois da cópia. Sem importar wheel remoto no Windows. Lock final
37nomes==versões/SHA256, sem extras/markers/URLs.37wheels+lock+manifesto,
39arquivos públicos/22.643.029bytes de wheels. Tetos/hash/nomes/contagem,
sem symlink/reparse/extra, secrets, catálogo, config ou material privado.
Código/testes/contexto/comando revisados antes de Docker. Tentativa real
única, estado consumido/fonte congelada. Missing/corrupt recusa; sem pull,
download, nova resolução ou reutilização parcial. Artefatos só Temp.

## Preparação Docker, instalação e commit próprios

Primitives de ownership/supervisão/Desktop pinadas da fundação, não seu
main. CLI/contexto/config/meta/estadoOff conferidos antes do start; não
alterar login/proxy/WSL/daemon. PreflightA registra inventory e imagemID
local exata/tagoriginal/DiffIDs/os/version/entrypoint/env. Preservar outras
cargas; nunca desligar Desktop sobre trabalho alheio.

Instalador próprio da imagemID exata: user0, rootfs **gravável só nesta
preparação**, capdropALL/NNP/networknone/restartno,512MiB memory e
memory-swap512MiB (swap adicional0),pids32/cpu1/nofile128/core0,shm8MiB e
tmpfs64MiB noexec/nosuid/nodev/uid0/mode0700. Perfil de preparação, não
operacional; nenhuma elevação de cotas após falha para obter verde.
Sem bind/socket/volume de host: docker cp do conjunto público para prefixo
próprio ausente na base, antes do start, tar/cópia validada. Não compartilhar
C: nem mudar file-sharing. Bootstrap/payload stdlib próprio pinado, nenhum
segredo em argv/env. Tudo entregue é material público do build.

Antes do pip: conferir39arquivos/hash/lock37 e bases do venv. Esperado
pip22.3.1 e setuptools65.5.1 do vendor ensurepip; medir e recusar qualquer
diferença sem revisão. Decisão inicial: **manter essas duas ferramentas**
no candidato para verificações/pipcheck. Inventariar distutils-precedence.pth
da base antes/depois; não alegar que não existe nem removê-lo para silenciar.
Os37wheels novos não têm .pth. Runtime mínimo futuro terá decisão própria.

Python-I-B/pip--isolated: no-deps/require-hashes/only-binary=:all:/no-index/
no-compile/no-cache-dir/find-links local. Configs pip e ambiente filho
explícitos, nenhum egress pelo networknone. Um pip filho supervisionado,
lifetime limitado dentro do namespace PID do container; pai/CLI mata e
recolhe o container próprio em falha/timeout. Não declarar cleanup só por
tentar kill ou abandonar filho. Nenhum backend/sdist é executado.

Após pip: pipcheck; instalado exatamente37+pip/setuptools. Bytes de cada
membro contra hashes/RECORD; RECORD reescrito é gerado. Validar também
arquivos gerados INSTALLER/REQUESTED/wrappers/eventualdirect_url local,
sem pacoteextra/pyc novo. Destinos .data explícitos se presentes; colisões
conflitantes entre wheels recusadas antes do pip. Nenhum downgrade/remove
de pacote para obter check verde. Ownershiproot/modos sem escrita de
grupo/outros em todo o venv/prefixo; não confundir modos ZIP e instalados.

Medir imports maskgw/bootstrap/MCP/Admin/PGWire/masking e os quatro
recursos UI da lista do produto; versões efetivas libpq/OpenSSL de
psycopg-binary e cryptography. SDK/transitivos só aceitos por compatibilidade
medida, não inferida do resolvedor. Nenhum config/catalog/DB/listener.

Remover apenas entradas da cópia gerenciada, por nome/hash/prefixotask,
preservando desconhecidos e recusando fechamento se aparecerem. Nada de
rm-rf genérico. Docker diff limitado ao venv e diretórios próprios previstos.
Commit do CID próprio parado, identidade/imagem/labels antes de mutação,
tagúnico. Salvar stdout commit e obter ID pelo inspect do tag, nunca parse
do stdout como ID. Restaurar USER10001:10001/workdir/entrypoint/env seguros
da fundação; nenhuma porta/volume/restart/HEALTHCHECK de disponibilidade.

## Sonda final e restauração

Segundo container próprio da candidata exata: user10001, rootfsreadonly,
networknone/capdropALL/NNP, mesmos512MiB/swap0/pids32/fds128/core0/CPU1,
tmpfs16MiB uid10001/shm8MiB. Repetir conjunto/imports/recursos/versões,
donos/modos e controles reais. Wrappers de terceiros existem declarados,
fora do PATH operacional; entrypointPythonabsoluto é a interface atual.

Cleanup só dos dois CIDs provadamente próprios/terminados, inventoryfinal
igual ao inicial antes de DesktopOff se iniciado por nós. Erro preserva
evidências/candidata em quarentena, sem retry/segunda carga. Não prometer
rebuild bit a bit de image (timestamps/commit): insumos/ID exato medidos.
Revisão de resultado antes de servir como fundação da integração real.

## Limites

Só app instalada/sondada offline se os gates passarem. Sem SQL, banco ou
container existente, segredo, listener/hostport, CI/CD ou operação pública.
Controlador ainda MCPstdio/EOF/SQL0A000. Foreground/worker/catalog/UI/
PGWire/MCPmultidatasource/IDE terão código/evidência próprios. D-119 segue
prospectivo até os testes próprios; preparo sem consulta não fecha
contenção/cleanup adversarial/sigilo entre workers ou qualquer gate aberto.

## Precisões incorporadas da revisão do desenho

O Claude2 não encontrou bloqueador de segurança. Divergência corrigida:
o wheel tem **cinco assets**; resources.load_resources() lê/verifica o
manifest.json (index/anchor) e devolve os **outros quatro** em RESOURCES
(index.html/ui.js/ui.css/presentation.json). Sonda deve conferir os cinco
bytes/hashes e chamar o loader que retorna quatro, sem ajustar a expectativa
para esconder arquivo faltante. Isso está em resources.py:22–27 e57–86.

Conferir as duas distribuições base antes do pip: esperado39 no final,
não pressuposto. distutils-precedence.pth executa o shim da base no startup
do Python: -I não equivale a -S. Mantido explicitamente só no candidato;
decisão do runtime final precisa tratar ferramenta/arquivo e patches
vendor. Avisos de versões upstream antigas do pip/setuptools citados pelo
revisor não são prova de vulnerabilidade destes RPMs Oracle (podem ter
backports). Antes de release, conferir advisories/changelog vendor ou
remover ferramentas de build em lote revisado, sem atualizar cegamente.
Nada aqui declara ausência global de CVE ou exige aprovação humana nova.

Instalar por nome via -r/--find-links, nunca cada wheel por caminho/URL;
gerados esperados: INSTALLER/REQUESTED/RECORD e oito wrappers listados no
I (cffi-gen-src/fastapi/httpx2/idna/jsonschema/mcp/pgpp/uvicorn). Direct_url
não é esperado nesse caminho e será recusado se aparecer sem explicação
revisada. Os37wheels não têm .data: mapear membros para site-packages.
Colisões conflitantes detectadas antes do pip; RECORDinstalled também deve
conter wrappers hashados/shebang absoluto correto. Não haver pyc novo,
sem confundir com pyc já fornecido pela base, que fica inventariado.

Docker cp sem -a deverá criar donos0:0, conferidos e recusados se diferentes,
sem adicionar CAP_CHOWN. Normalizar chmod só em entradas gerenciadas de
dono0:0:0644files/0755dirs, registrar antes/depois. HOME/TMPDIR ficam no
tmpfs, nenhuma gravação em /root ou prefixo não declarado. Commit sem
--pause depreciado; identidade vem do inspect do tag próprio.

Sonda mede separadamente: ssl.OPENSSL_VERSION (sistema), OpenSSL da API
pública cryptography backend, psycopg.pq.version()/__impl__binary e
OpenSSL_version(0) da libcrypto empacotada, caminho/hash fixados pelo I:
psycopg_binary.libs/libcrypto-e7530dde.so.3, SHA
3761d43a07bc3a119cfce159a0ae50b5fd526bd9db8bf9e87626487d12fc89cd.
Preferir RTLD_NOLOAD após importar psycopg para confirmar handle já carregado,
sem escolher por glob/busca de strings. ctypes argtypes/restype explícitos.
Esses imports **executam** os pacotes no Linux sem rede/configuração, o
objetivo da prova; não tratar como inventário passivo I. Imports do produto
devem manter ausência de listeners/conexões/config externa, com ambiente
mínimo. Qualquer efeito inesperado recusa o candidato e fica registrado.

## Primeiro incremento: somente montar o contexto no Windows

Código docs/poc/oracle9_install_context.py não invoca Docker/pip/import
de wheel. Captura programas próprios hashados I/builder só para admissão,
revalida D/arquivoIcompleto e fonte/ambos wheels próprios; os37arquivos
são copiados xb para raizTemp própria. Manifesto contém nomes/versões/
bytes/hashes, lock e projeção de arquivos instalados/owners/scripts a
partir dos inventários I aceitos. Qualquer colisão de membro regular é
recusada nesta política, mesmo se os bytes forem iguais. Nenhum .data ou
.pth no conjunto; oito wrappers declarados. Revalidar cópias completas e
origens de novo antes do ready. Se falhar, raiz consumida/parcial preservada.

Tetos32MiB porwheel/22.643.029bytes totais exatos/37wheels; evidências
fonte pinadas antes de JSON/EOF/expansão limitada do envelopeI. Manifesto
<=2MiB, lock<=64KiB; contexto tem39arquivos e somente os dois níveis
esperados. Nenhum arquivo do checkout ou dataset de origem é alterado.
24testes novos passaram;190relacionados:189pass/1skip de symlink Windows
anterior. Ruff/mypy do teste, format2 e E9/F63/F7/F82 do helper verdes.
Mypy inicialmente detectou falta de tipo numa lista da fixture; só a
anotação foi corrigida, sem alteração do programa. Snapshotv1 preservado,
v2 captura o teste final. Nenhuma cópia real de37wheels executada ainda.

Raiz preparada
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-install-context-20261026-4efda1b2,
taskf5d8480ea8e44fc5b37b37eee1ecf871, só state.json/invokedfalse.
Programa46108ce61026c09c1beb1c562ece6cad427a393d4d8e9e49f19853cc193f1907;
estado4f1b648dd558ad59573c462593e5d28271a691407470cd472368fda2a8ad6a0e;
snapshot oracle9-install-context-procedure-v2-20261026.json SHA
ff4718eed387d961254cc7b89c4866cce12089731c1fd5d3b4cfe2191912182a.
Conferir esses pins, fontes próprias/AppI, e estado fresco antes da chamada
única. Código/inputs congelados durante ela; nenhum Docker neste comando:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_install_context.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-install-context-20261026-4efda1b2'
exit $LASTEXITCODE
```
Só executar após revisão deste incremento/contexto/comando. Host/payload
da instalação Linux e seu cicloDesktop ainda não foram implementados.

Revisão pré-ação aceitou o comando de cópia único sem bloqueador. Precisão
menor sugerida: explicitar também identidade da linha de tamanho no zip
local. Mantido o programa pinado: check_wheelhouse do D, chamado antes,
já confere nome/hash/versão de cada linha do manifesto contra a projeção;
no loop local há ainda tamanho e hash reais. Não houve mudança de código
ou recalibração da entrada para executar. Instalação futura deve conferir
que oito wrappers não colidem com scripts já presentes em venv/bin.

## Payload nativo implementado, só revisão de código/fakes

Novo deploy/oracle9_offline_install.py, SHA
baca7707f7d4fe07fe08cc1b46892fdd6ba37e2e135399ef7df0908b9a330963,
sem chamador no produto. Comandos install/probe ainda não executados.
Profile exige Linux/Python3.11.13/venv/uidgid/core/fds/cgroup/CPU/network/
capabilities/NNP/seccomp/rootfs/tmpfs reais. PrepPID1 gera instalação e
attestation pública; probe readonly repete hashes/records/imports/versões.
Nem isso comprova os gates operacionais de worker/sigilo D-119.

Pip filho só por flags fechadas e env mínimo, stdout/stderr em arquivo
tmpfs supervisionado, timeout120s/limite lógico1MiB, killgroup/wait em
falha. NamespacePID1 ainda tem cleanup externo obrigatório pelo host;
nenhuma liberação por simples tentativa de kill. Logs públicos de falha
preservados em base64/hash no resultado, sem mensagem original de exceção.
Manifesto/source1382 e37records, generatedINSTALLER/REQUESTED/wrappers,
set39, baseline integro e ausência de extras conferidos. Attestation fora
do venv para evitar autorreferência, hash do arquivo será pin de probe.
Somente entradas públicas validadas são removidas, sem limpeza recursiva.

31testes novos passaram com prefixos/snapshots/Record/Processos fakes;
221relacionados:220pass/1skip anterior. Ruff/mypy do teste, format2 e
sintaxe do payload nos escopos declarados verdes. A primeira simulação
de timeout precisou declarar SIGKILL9 no mock Windows (o módulo signal
Windows não expõe esse nome); nenhum pip real ou processo foi morto.
O programa nativo ainda não foi executado, nem seu profile Linux medido.
Review só deste payload antes de implementar/validar host e comando real.

### B1 do payload reproduzido e corrigido antes de Linux

Revisão encontrou excesso possível de stdout em logs. Duas regressões
vermelhas primeiro: falha com3logs de1MiB gerava4.194.695bytes JSON;
sucesso com1MiB deNUL gerava6.291.575bytes JSON por escaping. Corrigido:
ambos os caminhos retornam só bytes/SHA do log inteiro, prefixo base64
deaté256KiB/prefix_bytes/truncated. Serializador confere JSON final
<=1,5MiB antes de escrever stdout; o host terá limite2MiB. Log completo
acima do prefixo **não fica preservado** após desmontar tmpfs/container.
Não interpretar o hash inteiro como cópia recuperável do texto perdido.

Precisão incorporada: exigir lib64->lib literal na base, antes de pip,
para explicitar mapeamento do platlib Oracle ao caminho físico inventariado.
Shebang/emptydirs/RTLD_NOLOAD seguem gates reais, sem alegar medição Linux.
34testes novos passaram; escopos estáticos anteriores verdes. Fonte atual
ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af,
22.752bytes. Ainda sem execução do payload, host ou Docker neste lote.

Rerevisão aceitou o payload ee2becec congelado, sem bloqueador. Apenas
o host e seu ciclo/controlos próprios ainda precisam de revisão pré-ação.

## Host e ciclo completo preparados, sem executar

Novo docs/poc/oracle9_offline_prepare.py, SHA
9abfb5bbe8dfcdfb69b836588256fdea269998e00fc13385b8c7473ab62f0ba2.
Reusa bytes pinados da fundação0b0bb171 e bounded58c692a7. Comandos só
desktop-linux, IDbase fixo/no-pull,39entradas verificadas antes/depois do
cp, dois CIDs/labels/task/source/manifest e profile antes de ação. Instalador
gravávelroot512MiB/swap0 e sonda nonrootreadonly512MiB/swap0, ambos
networknone/capdropALL/NNP/CPU1/pids32/fds128/core0/shm8MiB e tmpfs do
papel. Sem Docker/socket/volume/bind/port/extra capabilities.

Watchdog global600s não-daemon, prazo CLI run300s e Nativepip120s cada;
falha recusa sem retry/elevar recursos. Resultado Native JSON de uma linha
<=1,5MiB, stdout CLI limitado2MiB. **Stderr do CLI é descartado** pelo
bounded herdado, não misturado nem alegado preservado; stderr do pip é
capturado pelo payload nos prefixos públicos limitados. Erro do CLI é
registrado por exit/categoria, sem inventar sua mensagem original.

Output/inspect brutos guardados antes de inferir sucesso; install precisa
exit0/OOMfalse/Pid0/outcome correto. Cópia da atestação limitada4MiB e
SHA do stdout conferidos, gate diff estrito, commit sóparado sem --pause;
stdout guardado e ID pelo inspect da tag própria,3DiffIDs/prefixobase,
USER10001/entry/env/workdir/CMDesc vazio e sem superfície ativa. Tag
pretendida é registrada mesmo se commit/sonda falhar; candidato reprovado
não é promovido e imagem não é apagada automaticamente.

Cleanup sempre tenta somente CID/name cuja identidade completa confere;
depois do kill precisa stopped/Pid0 antes de rm semforce e psbem-sucedido
vazio para ausência. Mudança de fonte própria aborta trabalho, mas cleanup
usa código já capturado e pins CLI/contexto originais (não depende do
novo arquivo de payload alterado). Se criação ficar incerta, cleanup não
vira comprovado só por inventory vazio. Watchdog precisa terminar e
inventáriofinal ser igual a vazio inicial antes de autorizar DesktopOff.

31testes novos do host passaram: profile/args/ownership/diff/frame e cinco
roteiros completos com CLI fake (sucesso,cpfail,Nativerefused,sourcechanged,
foreignowner). Nenhum executa Docker/pip; thread real de supervisão termina.
255relacionados:254pass/1skip de symlink anterior. Ruff/mypy dos testes,
format e sintaxe dos scripts nos escopos declarados verdes. Um warning
inicial de regex bytes\s foi corrigido para rawbytes, mesmo comportamento.
Sem profileLinux/runtime real medido neste incremento.

### Raiz e pins do procedimento

Raiz C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-offline-20261026-4ae79da8,
taskc23dd3df7b4241b4b0757da3863f8f8a,invokedfalse/desktopunobserved/semphase.
Estado556204e41171e520fee3da3a757c00e60499ecc8c5d52f8d7f2a745b6869c7ec.
Controles clonados do ciclo já medido da resolução, adaptados só a
root/task/kind/profile/program/payload/pins/contextverify antes de start:
- start_desktop.ps1:63ae0bd0ba52fd7fb9715284fc8eb9de0302d31d765d44977e4cc730e2beca96
- state_control.ps1:d1c1c115d1ee3debef52db94bde48e22ad276db18b589996dcf5a9711f26e637
- restore_desktop.py:45b4daff6a814b5e047bf8045a66c5c370af7ff0ea74207606144166b5a400aa
Snapshotv2 oracle9-offline-procedure-v2-20261026.json SHA
801fe328601ae6f9a9972afa7e2a93a8f8b0ecf20fcca2079dad916dd1127424.
Snapshotv1 anterior mantido; ambos ainda sem ação. ParserPS dos dois
controles passou **sem invocá-los**. Fonte/data/controles serão congelados
desde A até restauração/Off, sem corrigir código com a rodada em curso.

### Comandos exatos previstos, após revisão

Antes de cada passo, conferir todos os pins completos acima, programa,
payload, fundação/helper, CLI/Desktop/config/meta, contexto/ready/lock,
pyproject/seed e snapshot. Primeiro passo exige estado inicial556204e4,
rootfresh sem result/observations/restore. Os demais conferem transição e
identidade, mantendo FileTimeUtc em Int64 (nenhum roundtrip JSNumber).

1. A: executar start_desktop.ps1 da raiz própria; ele confere contexto por
   Python-I-B antes de StartProcessHidden e registra se já estava ativo.
2. Observe separado3vezes via state_control.ps1 -Mode Observe; cada chamada
   espera3×10s, total9observações. Não alegar espera contínua se houver pausa.
3. state_control.ps1 -Mode Ready, somente depois das9observações válidas.
4. B/C, uma execução única:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_offline_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-offline-20261026-4ae79da8'
exit $LASTEXITCODE
```
5. Conferir result/cleanup/inventory/outputs; se Desktop eraOff e só nós
   iniciamos: state_control.ps1 -Mode AllowStop, Python-I-B restore_desktop.py,
   depois state_control.ps1 -Mode Off, com exits e ausência de processo
   conferidos. Se era ativo, preservar e registrar sem chamar stop.
6. Só após concluir/restaurar, conferir sources/entradas outra vez e
   registrar resultados originais/revisar. Nenhum próximo lote na rodada.

Nenhum desses comandos/CLI/Desktop foi executado neste incremento. A
imagem inicial Containerfile continua protótipo não utilizado. O candidato
se medido ainda terá CMD vazio da fundação, não daemon/MCP preso por stdin.
Produto com -m maskgw e futuro modo foreground/SQL são gates posteriores.

Revisão pré-ação completa aceitou A/Observe×3/Ready/B/AllowStop/restore/Off
sem bloqueador. Recomendação de recusar D no diff incorporada antes de A:
teste vermelho primeiro mostrou aceitação de remoção, depois regex[AC]
passou a recusá-la. Delta de programa é só esse caractere;32testes host e
256relacionados:255pass/1skip, estáticos declarados verdes. Conforme aval
condicional, não exige outra revisão desse delta; controles inalterados.

Pins finais que substituem a proposta ainda não executada acima:
programa401afa8cb18156e59016650ac4b87bf3186af1641685fdb05ea2fb7df5363fce;
estado inicial30a14fc490be4b1f7fb8236114a67ce4e4b031bc3bb69a3683ee2eb933dca107;
snapshotv3 oracle9-offline-procedure-v3-20261026.json SHA
9f4da3c159d5d73bbd1b5cd3333963b405c6bed350d3b4ef9563c241f89d4a0d.
Raiz/task e hashes dos3controles permanecem os mesmos.18pins estáticos
foram conferidos com exit0 antes de qualquer ação; ausência do Desktop
observada. O restante do procedimento e da única rodada não muda.
