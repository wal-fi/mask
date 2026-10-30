# Oracle9 — preparação do runtime Python

2026-10-23, escolha técnica sob delegação. Base9.8 realmente verificada;
não é instância do gateway. Próximo incremento prepara uma imagem local
com Python vendor, antes do fechamento de wheels Linux e worker.

## Contrato antes de código e execução

Não usar Docker build/BuildKit nesta rodada: encerrar apenas seu cliente
não comprovaria cancelamento do trabalho no daemon. Usar um container
efêmero identificado por nome/label/CID, supervisionado, depois commit do
container parado e uma segunda sonda read-only da imagem resultante.
Imagem resultante por content ID local, sem alegar RepoDigest publicado ou
build bit a bit determinístico. A receita por Containerfile permanece uma
preparação futura, não algo já executado.

Base local pinada, sem pull:
`sha256:d8c0a1f95f3394a2b40ece95dbff199cea94d06ac0ed354a7b88e96e2df5bb94`.
Do índice público oficial Oracle (consulta HTTPS limitada a12MiB/30s):
`python3.11-3.11.13-10.0.1.el9_8.x86_64` e
`python3.11-pip-22.3.1-6.el9.noarch`. A consulta mediu8.973.973 bytes,
SHA256 `16fd7141a6826e8db329a2acc63b6d315b819b4d36e5f62074fa0e467b2c4d77`.
Fonte https://yum.oracle.com/repo/OracleLinux/OL9/appstream/x86_64/.
Não confundir número upstream com ausência de backports Oracle.

Preparação só de pacotes públicos, sem projeto, DSN, chaves, token ou
catálogo. Root apenas neste container descartável para RPM; sem caps,
privileged, socket Docker, mounts ou portas. Rootfs temporariamente
gravável para instalação. Rede bridge padrão para repositórios públicos
Oracle, nunca host: ela **não é** allowlist de egress do kernel. Comando
fixo só consulta os repos ol9_baseos_latest/ol9_appstream e verifica GPG
conforme configuração vendor; não desligar assinatura nem TLS. Nenhuma
credencial corporativa/proxy herdada. Configuração repo e inventário RPM
devem ser registrados; resolução transitiva é mutável, não lock offline.

Perfil de preparação, não perfil D-119 de operação:512MiB memory/swap igual
(swap0), pids64, CPU1, shm1MiB, nofile256, core0, NNP, restartno/lognone.
Não testar pressão nem extrapolar estes limites para B-2. Filesystem
Docker não tem quota de disco certificada: só pacotes vendor e cache
transitório, depois microdnf clean all, sem dados de cliente. Sem aumento
automático ou repetição se falhar. Prazo instalação300s, stdout2MiB,
watchdog externo próprio420s que só mata CID validado. Criar sem start,
inspecionar configuração completa primeiro. CLIcreate20s/inspect10s,
commit60s. Filho CLI morto/recolhido não comprova sozinho fim do container;
inspecionar, parar/remover somente o próprio CID e confirmar ps restaurado.

Comando fixo: instalar exatamente os dois NEVRAs, criar venv em
`/opt/maskgw/venv`, inventariar todos os RPMs ordenados e registrar versão
Python/SSL/stdlib, limpar cache e criar diretório vazio. Nenhum pip remoto,
pip upgrade ou import maskgw nesta rodada. Recusar se o Python não for
3.11.13 ou os RPMs diretos divergirem. Capturar stdout original hashado;
nunca salvar log de banco ou configuração do usuário.

Somente exit0, sem OOM, identidade e runtime corretos permitem commit.
Commit de CID parado, tag própria exclusiva e label task; configurar
USER10001:10001, WORKDIR/var/empty, entrypoint Python isolado e CMD vazio.
Imagem sem VOLUME/EXPOSE/HEALTHCHECK/secrets, mantida para etapa seguinte.
Não excluir imagem ou tag anterior. Inspecionar imagem criada e depois
criar segunda sonda **sem rede, read-only, nonroot**,128MiB/swap0/pids16,
capsALL drop/NNP/fd64/core0. Importar apenas stdlib necessária, verificar
venv/Python/SSL/RPM manifest; não executar produto. Cleanup dos dois CIDs
próprios e inventário global antes/depois iguais (exigir vazio antes).

Desktop inicialmente off: início próprio oculto, identidade FileTime/PID,
observações/Ready conforme controles já corrigidos; restore somente após
terminal, cleanup confirmado e inventário vazio. Se pré-existente, manter.
Sem force/prune/alteração WSL. Procedimento exato, fontes/pins e comandos
serão revistos antes da primeira ação. Toda tentativa é consumida; falha
incerta vira registro diagnóstico, nunca replay ou mudança de pin/cota.

Sem job de retomada por cota não observada, segundo escritor, commit Git,
push ou liberação operacional. B-1/B-2/D-090 continuam abertos e SQL0A000.

## Fechamentos da revisão, antes de implementação

P1: inventariar NEVRA completo antes/depois. Cada par nome/arquitetura
preexistente deve continuar exatamente igual, sem remoção/duplicação ou
upgrade implícito. Nenhuma exceção de atualização está autorizada neste
procedimento. Conferir bytes de /etc/os-release e NEVRA oraclelinux-release
inalterados e IDol/VERSION9.8. Repos latest são mutáveis; a defesa é recusar
o resultado divergente antes de commit, nunca reinterpretá-lo como9.8.

P2: escolha exata **cap-drop ALL e nenhuma cap-add**, mesmo na preparação
root. Uma recusa do RPM/scriptlet por falta de privilégio é resultado válido
de falha, sem repetir a rodada nem adicionar capabilities automaticamente.
Registrar categoria/estágio/exit e cleanup, sem atribuição causal não medida.
Inspecionar o conjunto exato antes de start. Instalar sem weak deps/nodocs;
forçar gpgcheck e sslverify nos dois repos, sem --nogpgcheck. Inventário
inclui assinaturas RSAHEADER dos pacotes; não é auditoria de CVEs.

P3: base/preparação devem ter Env exatamente igual ao pin público da base,
sem proxy/variável extra. Depois da instalação, docker diff limitado e
persistido do CID parado **antes** de commit. Política para A/C: /usr,
/opt/maskgw, /var/lib/rpm, /var/lib/dnf, /var/cache/dnf e seus ancestrais;
/etc só passwd/group com apêndice literal declarado, ld.so.cache e arquivos
novos pertencentes aos RPMs instalados (relatório rpm -qf/hash no container).
Diretórios ancestrais C não autorizam conteúdo arbitrário. /root, /tmp e
logs extras recusados; limpar somente logs dnf conhecidos criados no
container próprio. Nenhuma exclusão de arquivo preexistente é aceita.
Qualquer caminho fora da política ou falha de prova recusa commit.

Criar entrada maskgw UID/GID10001 por apêndice literal no passwd/group,
recusando nome/UID/GID preexistentes; bytes anteriores devem ser prefixo
exato. HOME/var/empty, shell/sbin/nologin. Assim a sonda verifica pwd/grp
também, em vez de presumir compatibilidade de UID sem nome.

Commit define USER/WORKDIR/ENTRYPOINT/CMD[] e ENV explícitos. Env final é
base pinada mais HOME/var/empty, LANGC.UTF-8, PYTHONDONTWRITEBYTECODE1 e
PYTHONUNBUFFERED1; sem segredo/proxy. Recusar tag já existente antes da
instalação e reconferir antes de commit. Conferir config final exata,
label/task, zero volumes/ports/healthcheck e camadas da base mais uma.
Limites HostConfig não passam pelo commit: a segunda sonda aplica e
inspeciona seus próprios limites. Pip permanece nesta imagem **intermediária
de preparação** para resolver/instalar wheels; a imagem final e a remoção
de ferramentas ainda dependem de decisão/evidência própria.

Bridge alcança LAN/host.docker.internal; superfície aceita sob delegação
apenas para esta preparação sem dados/segredos de cliente, com comando
vendor fixo. Não é perfil de execução do gateway nem bloqueio de egress.

## Procedimento exato v1 histórico (não executado)

Fontes em `docs/poc/evidence/oracle9-python-procedure-20261023.json`,
SHA256 `8f8a0f201fba134c21f732c9e5efff272ccd15b6ab900b695e29f45563c2899a`.
Raiz própria `C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66`,
task1405edda0f844b4e8a5a5ae170c116c1. A/control/restore derivados somente
por root/kind/profile/task dos controles aceitos anteriormente. Nenhuma
ação em attempt antigo. Host usa helper bounded congelado58c692...;
watchdog próprio420s/contexto explícito. Programa e payload guardados por
hash no attempt; payload capturado uma vez, sem releitura após admissão.

Implementação: `docs/poc/oracle9_python_prepare.py` e
`deploy/oracle9_python_payload.py`. Trinta e oito testes puros de recusa
em `tests/test_oracle9_python_prepare.py` passaram, sem Docker; Ruff do
teste e format dos três arquivos passaram. Ambos os programas compilam.
Não são prova da instalação ou de runtime Linux. Não houve nova suíte
integral porque nenhum produto foi alterado.

Precisões incorporadas antes de executar: repo próprio de dois blocos
HTTPS em /opt/maskgw/repos, gpgcheck1/sslverify1 em cada bloco e flags
explícitas/reposdir exclusivo. Chave local vendor obrigatória, sem fallback.
Inventário rpm -V anterior é baseline: depois deve ser idêntico para os
pacotes antigos, exceto três arquivos declarados e conferidos separadamente.
RPMs novos exigem rpm -V vazio. /usr só aceita novos arquivos comprovados
por owner RPM novo, diretórios reais (não symlink) e estado do rpmdb.
Arquivos antigos /etc legíveis também são hashados; os ilegíveis não ganham
exceção no diff. C/tmp e C/var/tmp só se diretórios vazios. Logs dnf listados
só são apagados se criados neste container e ausentes do baseline; arquivos
preexistentes nunca são apagados. Sem limpar /root nem árvore arbitrária.
Env público da base é só PATH, comprovado pelo manifesto/config OCI público
com hash cruzado em `oracle9-public-image-config-20261023.json`.
Healthcheck NONE é explicitamente desabilitado; não é readiness.

Pins v1:
- start7cd1590261497430142c089ec1e1e063634235a0e9a6fc9172894156e66a6033
- control02c5e49aa2ba957081102a0a32761852ec321edeeeedcb728d59b747dc70c6f2
- restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28
- programa e8e087810805d4896bec0d03b931ca3ea2292e6e6060661afb9d4246bea80aad
- payload233e31bb50ad7106308ff2e4e10dbcd5e24daadcca222a9cb56c88dba13362aa

Comandos sequenciais, cada exit conferido e todos os pins rechecados antes
de ação; nunca colar como script que continua após erro:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\state_control.ps1' Observe
# Mais duas Observe somente após cada terminal0, depois Ready uma vez.
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66'
exit $LASTEXITCODE
# B terminal, cleanup/ps/identidade confirmados, somente se start próprio:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-2cb63b66\state_control.ps1' Off
```
Os exits explícitos pertencem a cada chamada separada do shell. Imagem
intermediária própria é mantida, nunca publicada. Nenhum registry push.

## Procedimento v2 histórico — correções antes da primeira ação

Revisão65351 encontrou B1 (pubkeys), B2 (custo por arquivo/relatório), B3
(/var/empty). V1 não executada, cópia preservada; mesmo attempt ainda
unobserved/invokedfalse. Scripts A/control/restore inalterados. Os mesmos
comandos acima só podem usar **os pins ativos abaixo**, após rerevisão.

- Chaves GPG separadas por versão/release, sem colisão de nome/arquitetura.
  RPMdb isolado em /opt/maskgw/keydb importa somente o arquivo local vendor
  antes de instalar. Chaves anteriores não podem sumir/mudar; qualquer
  chave nova precisa coincidir com esse conjunto local. Pubkeys ficam
  fora da verificação de pacotes normais. Nenhuma chave remota nova aceita.
- Ownership obtido numa consulta batch aos arquivos de todos os RPMs novos,
  sem processo por arquivo. Hashes/donos completos permanecem no relatório
  da imagem (teto8MiB); saída contém só caminhos/diretórios e hash/tamanho
  do relatório, máximo1MiB. CLI continua máximo2MiB, save4MiB. A segunda
  sonda confirma o hash integral. Inventário/assinaturas completos na imagem.
- /var/empty só aceito se vazio; testes positivos/negativos adicionados.
  Bytecode desabilitado para venv/ensurepip, sem `-I` nessa construção;
  processos de prova continuam `-I -B`. PYTHONDONTWRITEBYTECODE não é proxy
  nem segredo; export existe só dentro do comando após inspeção Env.
- Instalação permanece300s e commit60s; limites de memória/CPU iguais.
  Watchdog próprio prospectivamente1200s: inclui estágios de controle,
  commits, sonda e cleanup/transportes, não apenas o install. Não é teto
  do shutdown do SO ou prazo SQL. Nenhuma rodada anterior foi reexecutada
  nem houve aumento após falha real: ainda não há ação neste attempt.
- stdout/stderr do comando **interno público e fixo** reunidos em log
  limitado, com marcos BASELINE/INSTALL/VENV para diagnóstico; não há
  produto, credencial ou dado de cliente. Erros nativos do host continuam
  categorias fechadas, sem string/cadeia original. stderr inesperado do rpm
  continua recusando, mesmo se for limitação de cap-drop ALL.
- Imagem que tenha sido commitada em uma tentativa NOT_PASSED fica em
  quarentena: nunca usar como base, retaggear ou reaproveitar automaticamente.

42 testes puros passaram, incluindo múltiplas pubkeys e duplicação de
pacote, /var/empty e deriva do perfil. Ruff/format e mypy strict do teste
passaram; sem Docker. Pins ativos no JSON v2:
`docs/poc/evidence/oracle9-python-procedure-v2-20261023.json`,
SHA256 `e19b9ace06da5a0ca667a1af636629c7efac3cd93db4bf34010e43a4e1143b0b`.
Programa d2422d497eac92762b10c6e916f612834d6c9dafbc76aef393cd3a5f78890620;
payload553549611b2b9ef00855a4da5b857607ae5878aea73afa7807df0e229ca2d2cd.
A/control/restore mantêm pins da v1. Novo runtime ainda não medido.

## Pins ativos v3 — resumo comprimido com expansão limitada

Rerevisão65512 fechou B1/B3/tempo e recomendou folga no tamanho do resumo.
Antes de qualquer ação real, v3 usa zlib+base64 para caminhos/diretórios e
metadados: máximo2MiB antes de comprimir, base64 máximo1MiB, CLI2MiB
inalterado. Host limita a expansão a2MiB+1 e exige tamanho exato declarado,
tipo inteiro (não bool), eof e ausência de tail/unused_data. Truncamento,
concatenação, expansão excessiva e metadados divergentes recusados.
Não há descompressão ilimitada, nem aumento após falha real. Completo8MiB
permanece dentro da imagem e hash é confirmado pela sonda.44 testes puros
passaram, Ruff/format e mypy do teste aprovados. V1/v2 nunca executadas.

Ativo: `docs/poc/evidence/oracle9-python-procedure-v3-20261023.json`, SHA256
`5a8f6ad86c85cb196c7f1443795e2084e7c9d30e1b9d938c1f00c45e18a839f5`.
Programa2779f74205646a2840e83e08390ec79cf4802f96ae8f4ed7ab2be145b61861dc;
payload1f738b2fb6561f6d478a41ce987df2464b95b25a61e1e0a0f56cd54998631563.
Estado no Temp alinhado a esses pins, ainda unobserved/invokedfalse, sem
phase. A/control/restore e comandos sequenciais não mudaram.
