# Oracle9 — aplicação instalada e sondada offline em2026-10-26

**ORACLE9_APP_CANDIDATE_VERIFIED/exit0**, na primeira e única execução
real deste lote. Imagem local candidata:
sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a
tag maskgw-oracle9-app-candidate:c23dd3df7b4241b4b0757da3863f8f8a.
Somente fundação de integração/imports: sem processo Gateway disponível,
listener, porta, consulta ou release. B-1/B-2/D-090 gate2 e SQL abertos.

## Fontes, revisão e procedimento

Plano OFFLINE-INSTALL-PLAN e snapshotv3 9f4da3c1, root4ae79da8/taskc23dd3df.
Host401afa8cb18156e59016650ac4b87bf3186af1641685fdb05ea2fb7df5363fce,
payloadee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af,
estado inicial30a14fc4 e controles start63ae0bd0/state d1c1c115/restore45b4daff.
18pins conferidos antes de cada ação e novamente depois de Off. Nenhuma
fonte, controle ou contexto foi editado entre A e Off.

Revisões somente leitura do Claude2 aceitaram contexto, payload corrigido
B1 e ciclo completo antes de qualquer ação. Recomendação de recusar D no
diff incorporada/testada vermelha antes de A, com novos pins, conforme
aval condicional.32novos testes host e34nativos;256relacionados:
255pass/1skip de symlink Windows anterior. Ruff/mypy dos testes/format4/
sintaxe dos scripts aprovados no escopo declarado; não gate integral src.

A: contexto read-only revalidado antes de iniciar DesktopHidden; inicial
Off. Nove observações da mesma identidade em3chamadas Observe,90segundos
de espera comandada. Houve intervalos entre chamadas: não são apresentados
como espera contínua. Ready conferido antes do B único. Nenhum retry,
download, resolver, ampliação de recurso ou segundo escritor.

## Medição real

31comandos do corpo host, todos exit0,23,437s de soma das durações CLI
(não duração total da rodada). Dois comandos de restore também exit0.
Inventário inicial/final vazio; instalador e probe próprios removidos após
confirmação de término/Pid0. Watchdog não disparou. Stop só depois de
AllowStop/identidade/inventário; Off confirmado em
2026-10-26T14:04:01.0239836Z. Estado final COMPLETE_DESKTOP_OFF.

Base local1546afef inspecionada antes de create; sem pull. Contexto fechado
37wheels copiado para CID parado, dono0:0 conferido e modos normalizados.
Instalador root somente nessa preparação,capdropALL/NNP/networknone,
512MiB/swapadicional0/CPU1/pids32/fds128/core0/shm8MiB/tmpfs64MiB.
Pip somente local com todas as flags fechadas, sem backend/sdist/network.

Resultado instalado: **39distribuições exatas** (37lock+pip22.3.1 e
setuptools65.5.1 vendor), pipcheck aprovado.1.382arquivos de origem/RECORD
conferidos, além de INSTALLER/REQUESTED/RECORDreescrito/oito wrappers
gerados. Nenhum pacote/arquivoextra/novo pyc, colisão ou baseline alterada.
Baseline1.630paths; instalado3.332paths. Dono0:0, sem group/otherwrite
nem setuid/setgid; links existentes comparados sem segui-los. lib64->lib
literal confirmado. .pth de setuptools da base explicitamente mantido e
inventariado (executa no site startup); novos37wheels sem .pth.

Pipinstall log5.656bytes e pipcheck30bytes, ambos prefixos completos nesta
rodada/truncatedfalse, hashes no resumo. A política geral preserva sóaté
256KiB porlog, sem promessa de log completo quando truncado. CLIstderr
descartado pela primitiva herdada, nunca contado como preservado.

Entradas públicas gerenciadas removidas; diff1.710linhas só nos prefixos
declarados, sem remoções D. Atestação pública1.271.861bytes copiada/hash
conferido antes de commit. Commit do CID parado, sem --pause; ID obtido
pelo inspect da tag,3camadas com prefixo da base. Sem volume/porta/health
ativo, USER10001:10001/workdir/entrypoint/env da fundação e CMD vazio.
Não é daemon, nem manter stdin aberto para fingir serviço.

Probe real: UID/GID10001, rootfsreadonly/networknone/capdropALL/NNP,
mesmos512MiB/swap0/pids32/fds128/CPU1/core0, tmpfs16MiB/shm8MiB. Cgroup
memory.max536870912/swap.max0/pids.max32/cpu.max100000100000 e limites
conferidos dentro do namespace. Kernel6.18.54.1-microsoft-standard-WSL2,
não kernelOracle/RHELbaremetal/SELinux/FIPS. Os sete módulos do produto,
loaderUI e hashes dos cincoassets passaram sem config/catalog/DB/listener.
Pipcheck/records/prefixo/nativos repetidos como nonroot, sem novas escritas.

Versões **medidas separadamente**, não deduzidas de RPM:
- Pythonvendor3.11.13, sistema OpenSSL3.5.8 (25Aug2026).
- cryptography OpenSSL4.0.2 (25Aug2026), API pública do backend.
- psycopg binary, libpq180000 e OpenSSL3.5.4 (30Sep2025),
  OpenSSL_version(0) via RTLD_NOLOAD no caminho exato/hash do I.
Não se conclui que atualizar o RPM atualize libs empacotadas ou que este
inventário prove ausência de CVEs. Toolchain mínimo/patches e artefato de
release serão decisões/gates próprios; candidato tem ferramentas vendor.

## Evidências e integridade

Em docs/poc/evidence/:
- oracle9-offline-attempt1-20261026.json:298.688bytes,
  cb98f4b238a3f24e1a9d507f510cbe747da1b12340e7e0f2d6d82cf45ffa41cc;
  estados/observações/restore/result/rawinspects/stdouts/diff originais.
- oracle9-installed-attestation-20261026.json:1.271.861bytes,
  d47914864292c446e3d39591c9c60073f4ec3450b19893f2c577b8513f5d54bd;
  manifesto, snapshots completos e medição de imports/nativos.
- oracle9-offline-summary-20261026.json:11.587bytes,
  ad11e39d52e9eba6559a5f3606ebd7bd9be88e6495e881f0092097fd22fcabc5.

Após Off,18pins estáticos, contexto/ready/37wheels, fonte do projeto,
resultados e hash da atestação revalidados. FileTime de identidade mantido
como inteiro64nos arquivos originais, nunca roundtrip por JSNumber.
MCP/src/funcionalidade/dependências declaradas/.venv do host não mudaram. Nenhum banco
existente, secret, ação externa/porta, commit ou push. A revisão final do
resultado ainda antecede qualquer uso desta base na integração do worker.

Revisão final do Claude2 aceitou a imagem87871290 como entrada fixa do
próximo desenho, sem bloqueador de evidência. Conferiu39versões, piplog
local/pipcheck,3layers, profileUID10001, recursos/nativos e limitações.
Registro para gates futuros: OpenSSL empacotado3.5.4 é diferente/mais
antigo que o do sistema, e a política de patch dessa cópia requer exame
próprio antes de release. Manter a candidata para integração não é aceitar
automaticamente vulnerabilidades. Toolchainvendor/.pth, sigilo/proteção
de processos e domínioD-119 também ainda não constituem runtime final.
