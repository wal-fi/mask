# PG16 — admissão pública antes de qualquer credencial

2026-10-29, escolha sob delegação. Desenho antes do código/efeitos. T4v2
3a274347 aceita pelo Claude2: frame íntegro, EOFtrue, retain vivo após reap,
sete owners liberados. Não prova shell reader, PG ou worker. Plano NATIVE
continua com PKI/segredos só em memória, TLS verify-full/SCRAM, isolamento e
sem dados existentes. O logger/exportador públicos não serão usados com seed
privado ou resultados de consulta.

## Incremento mínimo escolhido

Primeiro builder/validador puro e fakes para um perfil PG16 público; depois
coordenador/proposta de uma rodada própria, revisados antes de Docker. Só
readmitir imagem local por ID e medir ferramentas/UID/mounts. Não executar
initdb/pg_ctl start/psql SQL/postgres servidor, criar role, rede ou senha.
Nenhum binário/flag BusyBox é presumido disponível: divergência para e
alimenta novo desenho, sem instalar/baixar ferramenta ou relaxar perfil.

Imagem proposta a readmitir:
`sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`.
Entrada sobrescrita por `/bin/sh`, fonte pública fixa/hashada via argv,
sem docker-entrypoint.sh, ENV explícito público e sem auth/proxy herdados.
Create pullnever; inspect imagem/Config e CID antes de start. Imagem ausente
ou Config inesperado aborta sem pull. Admissão de imagem não pressupõe seu
inventário a partir do tag; os fatos históricos16.15 são só candidatos.

## Perfil público e posse

Um CID próprio novo/task/labels/Intent, UID70:70, rede none, root RO,
capsALLdrop, NNP, sem override de seccomp, IPC/cgroup privados, sem namespace
host,512MiB RAM e MemorySwap igual, CPU1/pids256/core0/nofile128/shm8MiB,
restartno/lognone/healthnone, TTYfalse/OpenStdinfalse/StdinOncefalse.
Não há attach privado nem frame neste primeiro incremento: nenhuma entrada.

Tmpfs explícitos `/var/lib/postgresql/data`128MiB e `/tmp`16MiB,
uid70/gid70/mode0700/nodev/nosuid/noexec. Config.Volumes deve coincidir com
declaração conhecida da imagem; os mounts efetivos só podem ser os tmpfs
explícitos, nenhum volume anônimo criado a partir daquela declaração.
Mount inesperado aborta antes de start. Não apagar volume/recurso alheio.
Posse (CID/nome/task/labels/imagem/comando capturados) separada da aceitação;
mudança de fonte/perfil não impede remoção própria confirmada. Esses limites
são do ensaio e não qualificam memória total, B-2, C1 ou seccomp do kernel.

## O que a futura fonte pública medirá

UID/GID efetivos, `/etc/os-release`, shell/BusyBox e versões das ferramentas
`postgres --version`, `initdb --version`, `pg_ctl --version`, `psql --version`
(não servidores/SQL); presença executável de shell/base64/sha256sum/dd/wc/
timeout/stat. Ferramenta ausente é fato/recusa, sem fallback automático.
Tipos/donos/modos/tmpfs dos dois caminhos, sem ler diretórios do host.
Saída em schema fechado e com tetos antes de acumular; erros só categorias.
Versão exata não é presumida16.15 até medição. Hashes de binários públicos
podem servir à identidade da rodada; nenhum hash de seed/segredo.

O incremento seguinte do leitor shell deve provar, com dados públicos,
read exato/fragmentação/trailer/extra visível/timeout/EOF tanto presente como
ausente e recolhimento dos auxiliares. Presença de dd/timeout não é prova da
semântica dos flags: comandos concretos e negativos têm revisão e medição
próprias antes de receber segredo. Não afirmar que T4 Python mediu shell.

## Supervisão e sequência

Reutilizar só definições/coleta/idade/journal revisados, com programa/root/
kind/task/comando novos; nunca rerodar mains consumidos. Um writer, um ciclo
fresco, watchdog/cleanup antes de restaurar Desktop, inventário inicial/final,
ID/labels exatos, sem force/prune/retry. Código e orçamento concretos voltam
à revisão antes de invocar. Não presumir que o host T4, fixo na imagem621/
comando canário/UID10001, admite PG sem variante explícita.

Primeira entrega deste desenho é pura/fakes, não nova rodada nativa. Perfil/
argv/admissão de imagem e teste de volumes têm revisão própria; código
operacional/comandos serão lotes posteriores. Nenhuma dependência, instalação,
worker, ingresso, SQL ou serviço de produto ampliado.

## Precisões60182 incorporadas antes do código

P1 escolhido sob delegação: inventário de volumes antes/final por nomes exatos,
além dos CIDs; igualdade final obrigatória. Cleanup permite `rm -v` somente no
CID próprio com posse provada. Esse comando remove os volumes anônimos ligados
ao CID, nunca volumes nomeados. Nenhum `volume rm` direto, prune ou force.
Antes de usar -v, todos os mounts volume observados devem ter Name não presente
no inventário inicial; se um deles era preexistente, usar só rm sem-v para
desanexar o CID próprio, preservar os volumes e exigir reconciliação do
inventário/pendência. Volume novo que sobrar não é apagado por suposição:
HELD e recuperação específica revisada, Desktop não restaurado como sucesso.
Uma falha de inspect impede inferir anonimato/posse e mantém pendência.
Fakes devem cobrir volume inesperado criado no create (sem start), preexistente
preservado, named não removido pelo-v, erro no rm e diferença final/HELD.
Aceitação exige zero Mounts typevolume e HostConfig.Tmpfs exato; representações
de tmpfs não são convertidas em prova sem validação do perfil.

A fonte mede sha256sum, portanto não depende dele para verificar a si mesma.
Integridade pelo host: fonte pinada e Cmd/Entrypoint exatos no inspect antes
de start, sem auto-hash prometido no container. Formatter público shell em
linhas chave=valor fixas; parser host ASCII, teto de bytes/linhas, chaves exatas,
versões por regex fechada. Nada de salvar texto de erro nem stdout sem parser.
Entrada DEVNULL/stdinfalse via primitiva bounded revisada; coleta limitada.

S1 terá esperados próprios da imagem cf78 readmitida/pinada (Env/labels) mais
as labels próprias do CID e Cmd/Entrypoint da intenção; não herda ENV/labels
da candidata621. Imagem e CID têm gates separados, scan de chaves privadas
e Env exato. Esse incremento não autoriza o logger público para seed privado.

Referência primária conferida em2026-10-29:
[Docker: remover container e volumes anônimos](https://docs.docker.com/reference/cli/docker/container/rm/).
O-v também alcança volumes anônimos herdados; por isso a proteção contra
qualquer volume presente no inventário inicial é obrigatória antes de usá-lo.

## Precisão do perfil público — antes da primeira execução

Config.ExposedPorts5432/tcp é declaração herdada esperada da imagemPG16,
não bind/publicação. Imagem e CID devem declarar exatamente esse mapa;
HostConfig.PortBindings/PublishAllPorts continuam vazios e rede none.
Não declarar ausência dessa metadata da imagem nem remover a proteção de rede.
ENV da imagem só é admitido com chaves/valores públicos fechados; desconhecido
aborta antes de criar CID, sem descartar/normalizar campos para passar.
Imagem final só será readmitida no preflight futuro; fixtures são sintéticas.

Revisão36874, B1/B2: ulimits por mapa Name→(Soft,Hard), mais lista de2/chaves/
tipos exatos, sem depender da ordem não medida. Para ENV, escolhida opção(b)
sob delegação: nomes uppercase delimitados, sem PROXY/AUTH/PASS/SECRET/TOKEN/
KEY em qualquer caixa, valores públicos ASCII limitados, duplicata recusada.
PATH/PG_MAJOR16/PG_VERSION16.x/PGDATA exatos continuam obrigatórios. Extras
públicos de build não exigem inventar lista completa de nomes; ENV do CID
continua exatamente igual ao capturado da imagem, inclusive no S1. Isso não
é DLP/varredura genérica de valores; confiança na imagemID/daemon admitidos.
Raw local antes da validação/categoria fechada obrigatório no coordenador,
para tornar divergência de labels diagnosticável sem outra tentativa cega.
