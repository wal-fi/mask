# W1 — novo wheel e candidata de integração, sob delegação

2026-10-26. Desenho antes de novos efeitos. W1/D-121 revisado, 1266testes
relacionados verdes; sem chamador operacional. A candidata87871290 é anterior
ao guard/S1/codec/loop/owner. Não usá-la para fingir uma prova instalada W1.

## Primeiro incremento: somente novo wheel público, sem Docker

Reutilizar exatamente docs/poc/oracle9_app_wheel.py, SHA-256
a964890b2b6a3acaea87fcaeb0f780f14c0bc4b4656d8f983fb24b3e32a38507.
O helper já revisado captura o src atual fechado e pyproject fixado, sem
copiar .git, configs pessoais, testes, docs ou arquivos temporários. Seus
limites de512arquivos/16MiB e pins de projeto/inspector/backend/plugins
continuam; source_manifest será novo, não alteração da evidência anterior.
Fontes W1 devem ficar congeladas durante os dois builds e inspeção.

Preparar nova raiz própria Temp/maskgw-oracle9-app-wheel-20261026-<nonce>,
contendo apenas state.json kind oracle9-app-wheel-v1,invoked=false,task,
program_sha256, wheelhouse já admitido8ca7de53 e manifesto dos bytes atuais.
Nenhum efeito no checkout ou wheelhouse; antes de executar, conferir hashes
do helper e insumos e revisar estado/comando exato com Claude2. Um processo
`.venv/Scripts/python.exe -I -B docs/poc/oracle9_app_wheel.py <nova_raiz>`.
Helper consome sentinel, só backend setuptools84.0.0/wheel0.48.0/packaging26.3
admitidos, dois builds em cópias separadas, igualdade dos bytes e auditoria
de todos os membros/deps/RECORD. Não instala, importa app, acessa banco ou rede.
Falha aborta essa raiz sem retry; preservar prefixo/resultado para diagnóstico.
Não ajustar código/pins históricos para admitir build diferente.

Preparo concreto, ainda não executado: raiz
`C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-app-wheel-20261026-3ec5286b98824c32b262c704d464bf95`,
task39762fa4a61c427b869523d94d753bad. state.json SHA-256
9ec25dee492bb1481f190e89db5fa3820ad9c623752a77b56415772a64e37f21,
124arquivos/1525646bytes (inclui pyproject). Somente captura/preparo,
sem backend/install/import do app. Estado espelhado para revisão em
`docs/poc/evidence/oracle9-w1-wheel-preparation-20261026.json`, SHA-256
3dfdf3e636e680a9e245798a852ced21c386c1bba9313eba2f326b51fd69fed3.
Comando exato proposto, uma vez no cwd do projeto:
```powershell
& '.venv/Scripts/python.exe' -I -B 'docs/poc/oracle9_app_wheel.py' 'C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-app-wheel-20261026-3ec5286b98824c32b262c704d464bf95'
```

**Build consumido uma vez após revisão, exit0.** Resultado
APP_WHEEL_BUILT_VERIFIED, dois wheels idênticos448821bytes, SHA-256
6b63f239fadbc051f8fa850a96b69fbebba4f6b3eb12d3a12e49a9313429877b.
Nome/versão0.1.0 continuam iguais ao laboratório anterior; gates devem usar
esse SHA, nunca só nome/versão. Manifesto124 e127membros do wheel auditados;
mesmo projeto/deps, nenhum script/entrypoint/.pth/ELF novo. Rechecagem final
do checkout e dos dois arquivos wheel passou. Sem import/install do app.
Comparação exata com build anterior: cinco módulos novos listados no estado,
postgres.py e budget.py alterados;117entradas idênticas e nenhuma removida.
Relatório exato em `docs/poc/evidence/oracle9-w1-app-wheel-result-20261026.json`,
99190bytes/SHA0693d8533065289da5263b94fece42e865b06ca74282c94ca73ab2438bbff83e.
Estado de preparação acima é histórico, não permissão para reaplicar comando.
Evidência do build em revisão somente leitura antes de usá-lo na candidata.

Revisão final do wheel concluída: aceito como insumo fixo, sem alegação de
instalação/Linux. Identidade exclusivamente por SHA; os dois wheels0.1.0
nunca estarão juntos num find-links. Comparação do root completa117iguais;
revisor conferiu módulos/deltas/metadados dirigidos e declarou que não
recalculou hashes no shell. Esse limite não é omitido.

## Caminho seguinte proposto: atualizar só app na candidata existente

Evitar reinstalar36dependências que não mudaram. Em incremento próprio,
payload/host novos e revisados admitem a imagem87871290 e prefixo/atestação
originais completos; nova entrada fechada contém apenas wheel público novo,
manifesto e payload de atualização. Instalar somente maskgw por nome/hash em
lock de uma linha/find-links local com pip já inventariado, --no-index
--no-deps --force-reinstall --no-compile --only-binary=:all: --require-hashes,
em novo
CID de preparação próprio; nenhum container existente é modificado.

Antes/depois, verificar prefixo e RECORDs. Únicas diferenças permitidas:
package maskgw e sua dist-info exatamente conforme wheel novo/metadados de
instalação fechados. Todos os demais arquivos/links/permissões/versões devem
permanecer iguais; nenhuma dependência/console script/.pth/ELF novo.
Nova atestação referencia a anterior como histórico, sem afirmar que a antiga
ainda descreve o app atualizado. Imagem nova, novo relatório/manifesto/pins.
Sonda nonroot/RO/networknone via Python -I-B importa W1 do pacote instalado,
sem PYTHONPATH/checkout/fontes copiadas. Não roda SQL/worker ainda.

Essa direção reduz cópia e superfície de mudança; comandos/perfis concretos,
diferenças permitidas, cleanup e novo ciclo fresco são gates próprios antes
do código/execução Docker. Não presume que reinstall, artefato ou nova
atestação já existem. Pipeline velho de instalação/evidências não será editado.
Patches/minimalização de bibliotecas/pip/setuptools/.pth antes de release
continuam abertos, assim como W1 nativo/PG16/C1/B-1/B-2/D-090/SQL/produção.

## Desenho concreto para revisão antes do código

### Contexto público, sem Docker

Novo helper preparador, sem chamar main de helpers históricos. Reutiliza
funções puras capturadas/hashiadas do context46108ce6 para projeção de membros
e do buildera964890b para readmissão do wheel/manifesto/ferramentas. Inputs
fechados: atestação anterior d4791486 (1271861bytes), novo relatório0693d853,
dois wheels6b63f239 e src124 atual. Nenhum dado de config/catálogo/secrets.

Criar nova raiz/contexto público com exatamente manifest.json,
requirements.lock e wheels/maskgw-0.1.0-py3-none-any.whl. Lock literal:
maskgw==0.1.0 --hash=sha256:6b63f239fadbc051f8fa850a96b69fbebba4f6b3eb12d3a12e49a9313429877b
(com newline). Manifesto fechado referencia imagem87871290, atestação d479,
relatório/wheel novos e uma projeção instalada alvo. Esta projeção copia
as36dependências/console scripts/base_tools do original, substitui somente
os127membros do maskgw conforme inspeção nova e atualiza a linha do wheel.
Não manter lock_sha/source_app/contagem antigos como se ainda fossem atuais;
kind do alvo é novo, não alegar que esses36wheels estão no contexto físico.
Esperados1387arquivos projetados (+5), nenhum path removido do prefixo.
Snapshot base e versões39 permanecem os da atestação, sem novo resolver.
Fonte atual e ambos wheels rechecam no começo/fim; um sentinel impede retry.
Essa preparação terá fakes/revisão e comando próprio antes de materializar.

### Payload Linux instalador/sonda, ainda sem execução

Novo deploy/oracle9_w1_update.py usa bytes capturados e SHA ee2becec do
instalador anterior apenas como biblioteca no namespace privado (sem main).
Reutiliza runtime_profile, parent_environment, scan_prefix, base_pth,
versions, run_pip, verify_install, verify_record e imports_and_native,
sem alterar constantes/código das funções para forçar contagens antigas.
Não chama load_inputs/probe/install antigos, cujos contratos físicos
corretamente não admitem este contexto novo. Namespace só recebe PHASE
informativa para logs públicos, sem estado/credencial externa.

Antes de pip: PID1/root/perfil de preparação idêntico ao anterior, atestação
antiga exata/hashiada, scan_prefix igual installed_snapshot e verify_install
da atestação antiga sobre seu base_snapshot. Manifesto de entrada fechado,
um wheel+um lock por nome/hash, sem link/reparse/extra. Nome input sob
/opt/maskgw/w1-inputs-<task> já atribuído ao CID pelo host. Nada de mount/volume.

run_pip com install --no-input --no-index --no-deps --require-hashes
--only-binary=:all: --no-compile --no-cache-dir --force-reinstall
--find-links <entrada>/wheels -r <entrada>/requirements.lock. Depois pipcheck,
scan_prefix e verify_install(alvo, base_snapshot_antigo, snapshot_novo).
Esse verificador existente aceita projeção alvo de1387, não depende do
load_inputs com limite antigo1382. Antes/depois, arquivos de todos os outros
owners/base, links/modos/UID/GID/.pth/wrappers/versões exatamente iguais.
Para maskgw, só bytes/tipos/modos previstos no wheel/INSTALLER/REQUESTED;
todos RECORDs conferidos. Sem direct_url.json, entrypoint, .pth ou ELF novo.
Prefixo deve ganhar só5paths de arquivo, total3337 contra3332anterior;
dirs necessários já existiam. Se não fechar, abortar; não relaxar na rodada.

Importar módulos W1 instalados sem efeitos de rede/spawn em escopo de
contraprovas, além dos sete imports anteriores. Native versions devem
permanecer exatamente iguais à atestação anterior. Não chamar guard/main,
abrir worker, registry/datasource ou executar SQL. Novo scan após imports.
Nova atestação /opt/maskgw/oracle9-w1-installed.json referencia d479 e alvo,
snapshot e versões/native. Arquivo antigo preservado como origem histórica.
Inputs públicos removidos somente pela lista exata já verificada, sem rm-rf.

Sonda nova só aceita o hash da atestação nova vindo da execução; nunca cai
para a antiga. Confere prefixo/RECORD/versões/novo SHA de cada membro W1,
pipcheck e native igual, UID10001/RO/networknone/python-I-B e nenhum mount.
Nenhuma fonte copiada/PYTHONPATH. Mesmo perfil512MiB/swap0/pids32/CPU1/nofile128,
core0/tmp16MiB/shm8MiB já medido; preparação root tmp64MiB. Não é C1/pressão.

### Host/ciclo e alterações de filesystem

Novo host usa explicitamente desktop-linux/endpoint local e imagem87871290,
labels/layers originais. Imagem antiga/CIDs de terceiros preservados. Inventário
inicial vazio e preflight com exits conferidos, contexto/pins/CID/task exatos.
Ciclo fresco A/observações/READY e admissão B consumida dentro do runner,
com contador/UTC/boot e restauração pré-B nos termos NATIVE-CYCLE-PLAN.
Implementar os controles para esta atualização concreta, sem interface para
executar comandos arbitrários, callback de usuário ou backend genérico.

Novo CID parado, profile admitido antes de start; docker cp só contexto
público para path próprio. Depois start/wait/logs públicos limitados e diff.
Diff de overlay pode mostrar C até em arquivos de bytes iguais porque pip
reinstala o pacote inteiro. Permitir A/C só nos ancestrais necessários,
package maskgw/dist-info e A da nova atestação; cinco novos arquivos A e
RECORD C obrigatórios, nenhum D líquido/arquivo estranho. O scan/hash é a
autoridade de quais bytes realmente mudaram, não só o diff do overlay.

Commit Docker em nova tag/task/labels de wheel/atestação/manifesto, mantendo
origem por imagem e atestação; usuário10001/ENTRY-I-B/CMDvazio/ambiente anterior
fechado. Não é commit Git nem deploy. Novo CID da sonda contra esse ID novo,
mesma conferência, diff vazio e remoção dos próprios CIDs sem force. Cleanup
incerto/inventário divergente impede sucesso/stop, sem prune/retry. Image/tag
válida fica local como candidata; nenhuma porta, serviço ou restart habilitado.
Comandos, watchdog, tetos de output/duração, estados/artefatos e restauração
serão concretizados e revisados depois dos núcleos, antes de qualquer DockerCLI.

### L1–L3 e ajustes incorporados após revisão, antes do código

L1: além de verify_install, comparar **linhas inteiras** de scan contra o
installed_snapshot antigo. Seja M o package maskgw e sua dist-info:
- fora de M, igualdade exata de conjuntos/linhas, inclusive os RECORDs dos
  outros36owners, INSTALLER/REQUESTED, wrappers, modos, UID/GID e links;
- dentro de M, novos exatamente os5módulos; nenhum removido; bytes diferentes
  exatamente db/postgres.py, runtime/budget.py e dist-info/RECORD;
- todos os demais paths/linhas de M idênticos; dirs recriados iguais em
  modo/UID/GID, arquivos novos0644/root:root como os irmãos admitidos;
- duas fontes alteradas exigem bytes/SHA do wheel, RECORD exige validação
  completa do conteúdo instalado/allowedset, não SHA do RECORD cru do wheel.
O preparador registra os conjuntos explícitos a partir das duas inspeções;
o payload não infere um delta livre a partir do que o pip resolveu produzir.
Projeção antiga122members deve ser exatamente igual ao subconjunto owner
maskgw da atestação; nova127 sem colisão com nenhum outro owner. Copiar
console_scripts/base_tools inalterados, não alterar os36pacotes.

L2: fixar explicitamente os.umask(0o022) no payload antes de pip, junto do
gate PID1/root, pois o install antigo que fazia isso não será chamado.

L3: distinguir remoção **no scan final** de representação de overlay. A
hipótese de D opaco do revisor não foi medida neste host. Admitir previamente
as duas formas: sem D e D somente de diretórios do M que o scan final mostra
presentes e exatamente com a linha esperada. Nenhum D de arquivo ou fora de M;
nenhum path realmente ausente. Record pode aparecer A ou C em subtree opaco,
mas sua presença/hash/coerência serão conferidos. Cinco módulos novos ainda
exigem entradas A. Tests/fakes cobrirão ambas as formas. Terceira forma não
prevista aborta para revisão, sem mudar a regra na rodada.

Imports W1 separados da lista de sete de imports_and_native: a resposta
histórica permanece comparável; novos imports não adulteram esse objeto.
Stash ~askgw/temporários que sobrar faz o scan recusar. Nunca reaplicar pip
nesse CID: guardar logs/diff/metadata públicos antes de encerrar e remover
somente esse CID por identidade, se cleanup comprovável. Preservar evidência
de diagnóstico, não manter processo/container vivo só para repetir instalação.
Se cleanup não for comprovável, registrar/preservar ownership e não declarar
Desktop restaurado. Não usar remoção forçada nem apagar resource alheio.

Revisão do desenho aceitou arquitetura e pediu L1–L3/precisões acima como
condição para código/fakes. Implementação continua sem qualquer DockerCLI;
payload/host/procedimento terão revisões próprias antes dos efeitos reais.
