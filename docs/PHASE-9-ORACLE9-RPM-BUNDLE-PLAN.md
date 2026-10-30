# Oracle9 — bundle RPM fechado para o runtime

2026-10-23, desenho sob delegação, antes de implementação/download/ação.
Três tentativas anteriores preservadas em ORACLE9-PYTHON-VALIDATION. A
última resolveu nove pacotes e não teve OOM, mas a transação erro-1 não
identifica a causa. Não atribuir a caps sem prova. Nenhuma imagem pronta.

## Caminho mais direto

Congelar os nove NEVRAs realmente resolvidos, baixar só esses RPMs públicos
via HTTPS Oracle para diretório próprio limitado, registrar SHA256/bytes e
URLs finais, verificar assinatura com a chave da base pinada e instalar por
transação RPM explícita. Não carregar de novo metadados de todo AppStream.
Sem solver remoto, upgrades implícitos, --nodeps/--nosignature/--noscripts.
O download não instala nada no host. Toda dependência é conferida por
`rpm --test -i` antes da transação real; recusa sem buscar pacote extra.

Pacotes do log v5, todos novos:

| Repo | NEVRA |
| --- | --- |
| baseos/latest | expat-2.5.0-6.el9_8.7.x86_64 |
| appstream | libnsl2-2.0.0-1.el9.x86_64 |
| baseos/latest | libtirpc-1.3.3-9.el9.x86_64 |
| appstream | mpdecimal-2.5.1-3.el9.x86_64 |
| appstream | python3.11-3.11.13-10.0.1.el9_8.x86_64 |
| appstream | python3.11-libs-3.11.13-10.0.1.el9_8.x86_64 |
| appstream | python3.11-pip-22.3.1-6.el9.noarch |
| appstream | python3.11-pip-wheel-22.3.1-6.el9.noarch |
| appstream | python3.11-setuptools-wheel-65.5.1-5.el9.noarch |

Origem fixa https://yum.oracle.com/repo/OracleLinux/OL9/{repo}/x86_64/getPackage/{NEVRA}.rpm.
Allowlist literal dos nove nomes, sem entrada de usuário. TLS normal,
sem proxy/credenciais herdados, redirects só mesmo host HTTPS; não seguir
para LAN/host externo.30s por resposta,16MiB por RPM/64MiB total, leitura
em chunks64KiB; nove tentativas únicas, sem retry. Magic RPM obrigatório,
arquivos criados exclusivos, flush/fsync e manifesto fechado. Falha
consome download, preserva parcial para diagnóstico sem reaproveitar.
Hash de transporte não substitui assinatura; esta é verificada no Linux.

## Instalação isolada, papel de construção distinto do gateway

Container instalador **networknone**, sem mounts, portas, socket Docker,
secrets/projeto/DB; memória2GiB/swap0, pids64/CPU1/fd256/core0/NNP e sem
restart/logs como na v5. Novo lote não aumenta memória/tempo. Bundle só de
RPMs e programas públicos próprios via `docker cp` em CID parado, após
profile/identidade; entradas e hashes conferidos antes da cópia e dentro
dele. Não copiar checkout, frontend privado, .venv, chaves ou configuração.
Recusar symlink/junction/reparse, arquivo extra, nome/path inseguro ou
alteração. CLIcp limitado no tempo; depois inspecionar o mesmo CID.

Escolha técnica **prospectiva** para instalador root: cap-drop ALL mais
CHOWN,DAC_OVERRIDE,FOWNER,SETFCAP,SETUID,SETGID,SYS_CHROOT, conjunto exato
inspecionado antes de start. São operações normais de arquivos/scriptlets
do RPM; SYS_CHROOT é a única SYS, só no rootfs próprio, sem mount/hostpid/
privileged/NET_RAW/NET_ADMIN/SYS_ADMIN. Não é prova da causa da v5 nem
permissão do gateway. HostConfig/caps não passam pelo commit; sonda final
continua UID10001/capdropALL/read-only/networknone128MiB. Aceite só depois
de revisão deste novo papel de construção, sem elevar durante uma rodada.

Verificar magic/hash/NEVRA de cada RPM e `rpm -K` exigindo assinatura, com
chave local vendor importada; RSAHEADER keyID de cada pacote entre as
chaves locais permitidas, não só assinatura registrada. Executar uma vez
`rpm --test -i` e depois `rpm -ivvh` (logs públicos detalhados limitados).
Não repetir a transação nem usar override se ela falhar. Capturar saída,
status de container e inventário antes de remoção. Manter gates de base
inalterada, rpm -V, diff por owner, passwd/group literais, config/Env/camadas
e commit somente após exit0; remover só RPMs próprios conferidos antes
de commit, mantendo manifesto público. Imagem falha em quarentena.

Controles Desktop, admissão de tentativa própria, prazos300s/commit60s/
watchdog1200s/CLI2MiB, resumo comprimido e cleanup se mantêm. Procedimento,
fontes/pins e comandos exatos devem ser revisados antes da primeira ação.
Sem produto, banco, worker, SQL, B-1/B-2/D-090, deploy ou disponibilidade
certificados. D-119 de execução não muda por esse perfil de preparação.

## Fechamentos antes de código, revisão25259

B1: usar **`rpm -ivh`, um único v**, sem debug -vv por arquivo, sob o
mesmo teto stdout/stderr2MiB. O CLI RPM emite seus erros diretamente;
não prometer diagnóstico específico nem gerar log ilimitado. Excesso
continua falha fechada/cleanup, nunca ampliação durante a rodada. Isso
substitui -ivvh citado acima, sem novo logger/arquivo volumoso na imagem.

Política assinatura na consulta/test/instalação: `_pkgverify_level all`,
rpm -K deve conter signatures OK e não NOKEY/NOT OK, RSAHEADER keyID
entre chaves do arquivo local. Nenhuma flag de bypass. Exigir nos headers
que FILEMODES não tenha6000 e FILECAPS seja vazio/(none); depois verificar
modo real e xattr security.capability nos arquivos novos antes do commit.
Não basta registrar esses atributos. Exigir Caps como conjunto exato,
normalizando só alias CHOWN/CAP_CHOWN, sem duplicados e CapDropALL.
Mantido conjunto7 declarado para o **builder público sem rede**; revisão
o aceitou como defensável, redução3 era opcional. Um sucesso com mecanismo
e caps diferentes não identifica a causa da v5; interpretação fixada antes.

Download usa curl.exe nativo existente8.21.0, SHA256
`73d24149ff289afc49ec41f08918ef9faa727d39ad993e929757dc2ddafab805`,
não subprocesso do redirector Python/venv nem instalação de ferramenta.
`-q` primeiro ignora curlrc; `--noproxy *`, `--proto =https`, sem -L e
sem redirects; TLS padrão Schannel do host, sem insecure/autenticação.
`--max-time30`, connect10 e --max-filesize16MiB (ou saldo total menor),
supervisão externa35s/reap do próprio curl. Nome/URL literal, nove arquivos,
total64MiB, origem final exata, status200, magic RPM e SHA/bytes. Não usar
urllib que herde proxy ou timeout só por read. Em8.21 o teto de filesize
também vale durante transferência sem Content-Length, conforme
https://curl.se/docs/manpage.html#--max-filesize.
Zero redirects é refinamento restritivo da política anterior. Falha não
repete download, e nenhum RPM é executado no Windows. Manifesto/hashes
e fontes exatas terão revisão antes do download e do Docker separados.
