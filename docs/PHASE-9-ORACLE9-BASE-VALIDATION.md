# Oracle Linux 9.8 — base local verificada

2026-10-23. Somente metadados da imagem oficial; não é uma instância do
gateway nem fechamento de B-1, B-2 ou D-090. A opção A/D-119 foi aprovada
explicitamente para o perfil de teste local, com controles ainda pendentes.

## Duas rodadas distintas

A primeira, raiz `542c878d`, terminou NOT_PASSED. Pull e image inspect
passaram; a supervisão não devolveu o resultado de create. O container
próprio foi recuperado por identidade e removido sem start. O motivo
permanece desconhecido. Eventos posteriores somente de leitura registram
create/destroy, sem explicar a falha. Desktop restaurado off. Registro
imutável: `docs/poc/evidence/oracle9-base-attempt1-20261023.json`,
9.183 bytes, SHA-256
`24f9e181b2dd5d54069be3031a014004c6988f55d0bcccd44f4455e756f04359`.

O diagnóstico novo, raiz `700c8624`, task
`bae87fe0b3084922942da5889c8a56be`, foi preparado e revisto antes da
execução, com uma única chamada B. Não repetiu pull. O prazo de create
foi declarado prospectivamente como 20 s, sem alterar cota de memória ou
prazo de consulta/job. Fontes v2 em
`docs/poc/evidence/oracle9-base-diagnostic-procedure-v2-20261023.json`,
SHA-256 `4049e99793ce312ecaddec28fae9bc5e0de18164dcc352bef61b02ea8be569c5`.

## Resultado do diagnóstico

- A iniciou Desktop próprio, antes off. Nove observações reais positivas
  precederam Ready; PID e FileTime exatos preservados no artefato.
- B terminou exit 0, `BASE_METADATA_PASSED`. Todos os dez comandos da lista
  terminaram exit 0. Create: 0,172 s; leitura anexada: 0,360 s.
- Imagem linux/amd64 oficial, ID e RepoDigest
  `sha256:d8c0a1f95f3394a2b40ece95dbff199cea94d06ac0ed354a7b88e96e2df5bb94`.
  `/etc/os-release` confirmou `ID=ol`, `VERSION_ID=9.8`.
- Engine 29.7.2; kernel real `6.18.54.1-microsoft-standard-WSL2`.
  Userland Oracle não certifica kernel Oracle/RHEL ou SELinux de outro host.
- Cgroup v2 `0::/`; memory.max 134.217.728 bytes, memory.swap.max 0,
  pids.max 16. Campo kernel presente em memory.stat não é prova de
  contabilização completa nem da ausência de nokmem.
- core_pattern `|/wsl-capture-crash %t %E %p %s`, suid_dumpable 0.
  Não foi provocado core nem comprovado sigilo de dumps de um worker.
- Python 3.11 ausente nesta base. Nenhum runtime do gateway executou.
- Container próprio sem rede/portas/mounts, rootfs read-only, UID65534,
  cap-drop ALL/NNP, limites e comando inspecionados antes de start.
  Exit 0 e OOMKilled false. Removido por CID; inventário global vazio.
- AllowStop, restore e Off terminaram exit 0. Ausência de processos Docker
  observada às 20:30:28.9419328Z; não é prova de desligamento da VM/WSL.
  Imagem mantida em cache; nenhum prune ou alteração de host.

Create <=5 s não explica o NOT_PASSED anterior. Relógios host/daemon não
foram sincronizados quantitativamente; preservar as duas medições.

Cópia imutável das saídas originais, hashes, tamanhos e exits externos:
`docs/poc/evidence/oracle9-base-diagnostic-result-20261023.json`,
13.176 bytes, SHA-256
`c907ae13ae153791de764b222a7b075039453a0691a93f9fab9327bb5299dd51`.
JSON inclui UTF-8 exato; FileTime e nanossegundos não passaram por Number
JavaScript. Fonte de B é a v2 revisada, não a v1 histórica.

Não houve banco, SQL, worker, build do produto, commit, push ou deploy.
Próximo: runtime e fechamento de dependências Linux em preparação própria,
sem instalar nada no Windows. Só anunciar disponibilidade do gateway após
os testes de aceitação reais.
