# Oracle9 — relatório de resolução Linux medido (2026-10-25)

**LINUX_DEPENDENCY_REPORT_PASSED**, apenas relatório, sem instalação ou
lock instalado. Preparação sob delegação; código/plano revistos por22631,
delta de diagnóstico por5531, correção integral dos controles por82020.

## Histórico preservado e execução

A da raizf74abc9d falhou antes de reserva/launch, BUNDLE_NOT_READY herdado
do controle RPM. Nenhuma rede/pip/Docker nessa tentativa, zero processos
observado; artefato5196eff9 em DEPENDENCIES-PLAN. Corrigido sem inventar
campos de bundle e nova raiz9ed658f2/taskd8c06b17ed9e4287aff515719d5bcf1a.
Snapshotv4 SHA448508cd; Python host55c1eedd/payload011ba374, pyproject917fe735/
seedfd77310a, imagem fixa1546afef. Prefixo somente leitura do start foi
conferido antes da revisão, fora de A, sem escrita de estado ou launch.
A/Observe3/Ready/B/AllowStop/restore/Off separados, todos terminais0; uma
resolução nativa, sem retry/replay, fonte imutável/pins completos até Off.

## Medições

- 11 comandos CLI com exit0, resolução10,407s/exit0. Watchdog não disparou,
  container exit0/semOOM, CID próprio removido, inventário vazio.
- Restore0 e Offtrue em **2026-10-25T23:49:21.8185723Z**. Nenhum Docker
  ativo ao término, sem afirmar que a VM WSL foi parada.
- Inspect bruto da imagem final agora guardado, com DiffIDs:
  c8033153c9465fa4e4f02df8b57cda30011514f5b1e7438bf521776e63f0abaf e
  9a40c1add57e0336e3d66b67f5495c053b7e9dcdc8a635a155570174d926b44d.
  Apenas1546afef usada; imagem antiga23b754ea em quarentena não foi usada.
- Kernel6.18.54.1-microsoft-standard-WSL2, Engine29.7.2, overlayfs/cgroupv2,
  MemTotal16.689.963.008bytes (elegibilidade, não RAM livre). Info reduzido
  a campos públicos, não guardou campos proxy. UserlandOracle9.8, não
  certificação do kernel Oracle/RHEL ou SELinux.
- Config do container conferido antes/depois e bruto preservado: UID10001,
  rootfsRO, capdropALL/NNP, bridge sem portas/binds/mount externo, tmpfs/tmp
  128MiB/noexec/nosuid/nodev, memória512MiB/swap0/pids32/CPU1/fds128/core0.
  Sem teste de pressão ou evidência nova de domínio completo de memória.
- Pip22.3.1 medido, formato0 e archive_info.hashSHA256. --dry-run/
  --only-binary/--ignore-installed; nenhum setup.py, build backend ou import
  de pacote selecionado, nenhum pacote instalado. Índice PyPI fixo, **sem
  filtro de egress da bridge**, exposição pública sem dados/credenciais
  aceita prospectivamente sob delegação. Não alegar isolamento de rede PyPI.
- CA do sistema em /etc/pki/tls/certs/ca-bundle.crt, resolve para
  /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem, root0444/223.752bytes,
  SHA00411c197b16f659945fba3c2f970a26030f56eef5d445c913cb59a089c813b9.
  --cert explícito, sem trusted-host, proxy ou credenciais do host. Três
  configs pip ausentes e ambiente reconstruído confirmados pelo payload.
- Stderr127bytes: aviso esperado de --report experimental; inteiro/hash
  preservados. Não convertê-lo em falha nem ocultar outra saída.
- Relatório bruto404.801bytes,
  SHA877635a315fbbfecc567d6f924d1616182b931c39f111e64a33e7af8fa96ace3,
  envelope163.350bytes,
  SHA6d8076deb5570e5cc1a3e0d01296bb6f8b841e6a8d0baf6565caa834e7155ceb.
  Original comprimido validado por bytes/hash/EOF/sem cauda, projeção
  rederivada e comparada no payload, host e novamente após Off.
- **36 wheels selecionados**, todos os pins diretos presentes/satisfeitos,
  nenhum pacote Windows/musllinux/macOS/plain-linux. Tags manylinux x86_64
  até glibc2.34 medida. URLs canônicas files.pythonhosted.org e SHA256.
  Lista completa com versões/URLs/hashes/RequiresDist no resumo imutável.
  Transitivos são os selecionados nesta resolução, não versões da baseline
  Windows. Compatibilidade executada do app ainda não foi medida no alvo.

## Artefatos e escopo dos gates

Completo `docs/poc/evidence/oracle9-dependencies-attempt2-20261025.json`,
250.020bytes/SHA8b737f8fe07f6ec42d8984fec013bf43bdf483e3629a04cf3390b3b9f4807113.
Resumo `oracle9-dependencies-resolution-summary-20261025.json`,34.504bytes/
SHA3866fb9f424c38beeee963b34e68d2ec325c53e88407590d0a243b91bb498b20.
Inclui inspect bruto base e containers antes/depois, contextos/observações/
state/restore, stdout integral com relatório comprimido e projeção.
Não passar FileTime/inodes por Number JavaScript ao copiar; bytes UTF8
originais são preservados. Bruto do daemon com proxy não foi persistido.

63 testes novos/217 relacionados puros/fakes no Windows3.11.3 passaram,
Ruff/mypy dos dois novos testes e format de4arquivos. E9/F63/F7/F82 dos
scripts passou antes do último campo de daemon-info; não afirmar lint
completo dos scripts. Nenhum src/produto/UI/dep/.venv alterado; suíte
integral Python/Node/browsers não foi repetida neste lote de preparação.

Próximo, depois de revisão desta evidência: download fechado dos36arquivos,
limites por arquivo/total, hash obrigatório e inspeção segura de wheel,
sem executar no host; build do wheel próprio e instalação **offline**
com --require-hashes/--only-binary/--no-index em perfil novo revisado.
Isso ainda não é lock final instalado ou auditoria de segurança de todos
os pacotes. B-1 fim a fim, B-2, D-090gate2, SQL e produção continuam
abertos; Gateway ainda indisponível. Nenhum DB existente, commit/push ou
serviço operacional foi alterado/iniciado. Nenhum job/cota/outro escritor.

Revisão final34268 confirmou a evidência sem bloqueador para usar as36URLs/
hashes como candidatas fechadas de download. Corrigido apenas o erro
documental121→127bytes do stderr a partir do valor medido no envelope;
artefatos e contagens de testes intactos, sem reexecução. Aviso é somente
experimental, sem yanked ou outra anomalia observada. Procedência dos
nomes novos, orçamento/ZIP/RECORD/entrypoints e política de libs nativas
serão tratados no próximo desenho antes de download.
