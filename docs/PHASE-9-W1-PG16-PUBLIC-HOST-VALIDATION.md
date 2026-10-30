# PG16 público — coordenador isolado, CLI simulada

2026-10-29, implementação sob delegação após o desenho6796 e aceite17011
do monitorb86841ea/emergência54cc8f68. Nenhum novo DockerCLI, laboratório,
container, PG/SQL, seed, segredo, root operacional ou serviço neste lote.
Sem main/chamador operacional: entrada/exportador/preparador e comando exato
continuam futuros, com revisão antes de qualquer efeito.

## Fonte e composição

`docs/poc/pg16_public_host.py`, SHA-256:
`d63650d614d03f7b117ee8fbd2392b19ac560c0e68b4cba8ec9769c814eac0ef`.

Subclasse explícita das definições congeladas4bc/b593, sem invocar seus mains.
Captura sete colaboradores por hash: ownera02f/perfilfe2f/adapterf1d9/
volumes6e38/identitydc24/emergency54cc/watchb868. Usa o namespace do perfil e
Target do owner, preservando igualdade de tipo exato. Fontes consumidas
anteriores intactas. Pins de código capturado servem no cleanup; pins do
CLI/PS/config/endpoint continuam vivos e obrigatórios.

CLI por formas fechadas, sem install/copy/commit/pull/exec/volume-rm/prune.
Start attach só pelo owner DEVNULL, registrado antes de spawn; Birth pelo
handle original publicado sincronicamente no retorno/falha de start e após
quiesce, sem adivinhar PID. Oito overrides do owner continuam os revisados.
Supervisão PG própria com lock comum, heartbeat/ack e sem release na thread.
Jornal12/replay/ciclo fresco são herdados; o driver operacional ainda falta.

Preflight exige daemon/kernel corretos, inventário de CIDs vazio, readmissão
da imagemcf78 e inventário inicial de volumes com exit0. Blueprint/medida
antes de A coincidem com Intent real. Baseline tem idade máxima30s e nova
listagem igual imediatamente antes de create; tempo conferido também após
a listagem. Não é exclusão global de outros projetos nem garantia contra
mudança externa posterior. Intent é durável antes do efeito; somente um
create, CID vem só da resposta exit0, ambiguidade mantém HELD sem retry.

Config/perfil/mounts são validados antes de start. Unexpected volume aborta
o probe; identidade conservadora ainda permite cleanup do próprio CID.
Quiesce positivo/ticket antes do lock/cleanup. Own-inspect, kill se necessário,
reinspect Pid0, decisão durável antes de rm ou rm--volumes; autorizações de
kill/rm são internas e consumidas antes do efeito. Sem-v para preexistente
ou incerto; named novo que sobra mantém HELD. Nunca apagar volume diretamente.
Ausência nova, reconciliação por conjuntos completos e persistência de
metadados antecedem close do owner. Remover CID não prova volume restaurado.

Inventários completos/raw em arquivos `local-*`, incluindo a baseline local
de recuperação, devem ser retidos pelo exportador futuro. Metadados públicos
só contagens/hash canônico, deltas e nomes anônimos novos64hex ligados ao CID
próprio; `ownership.json` não inclui conjuntos completos. Raw de cada reply
é xb/fsync antes de parse/validação, inclusive exit ruim; manifesto associa
índice/tamanho/hash/exit. A saída completa do probe é local antes do parser.
Nenhum prefixo ou erro aprova facts. Isso ainda não implementa o exportador S1.

Probe aprovado requer report inteiro/exit0/EOF pelo owner e inspect parado,
Pid0/semOOM/semDead/exit0. Cleanup, inventários CID/volumes e join são necessários
antes do Desktoprestore; volumes conferidos novamente antes do stop. A CLI
recusa stop direto sem autorização interna. Orçamentos desenhados B90,
cleanup25 após quiesce6, restore93/join55 preservados, não teto do SO.

## Gates e histórico honesto

Primeira seleção:31passed em7,94s com fake CLI/owners/inspect/report/volumes.
Ruff/mypy encontraram só problemas de typing/lint do teste, corrigidos.
Revisão própria adicionou cinco regressões: rm-v direto sem decisão, baseline
antiga, baseline alterada, stop direto e retry do argv após create ambíguo.
**Todas falharam antes do fix** (5failed/31deselected em1,27s). Os dois efeitos
indevidos chegaram ao fake e foram recusados pelas asserções dele; não foi
Docker real. Seleção final: **36passed em8,21s** no Windows3.11.3, sem skips.
Ruff src/tests, lint restrito do helper e mypy strict311/314323 limpos;
format324 (src/tests+host) limpo. Helpers não são declarados mypy-strict.

Casos cobrem fluxo normal, mount novo anônimo/preexistente/named/unknown,
nenhum start após perfil recusado, exit inicial ruim, criação ambígua,
inspect alheio, rm/ausência/ticket/delta final incertos, falha start/report/
estado rodando, minimização, raw antes de validação e flag só após persistência.
Nenhuma thread de monitor, PS, subprocesso ou função nativa de identidade
foi executada por estes testes. Não equivalem a prova do SO do destino.

O timing histórico reprovado de `test_pending_spawn...` e sua repetição limpa
continuam em PUBLIC-CLEANUP-VALIDATION, causa indeterminada. Não foi apagado
nem convertido em alegação de estabilidade por este lote.

## Rerevisão de configuração e autorização de stop

Review61744 recusou d63650d6 por persistir o bruto de `docker info`, que
poderia incluir configuração de proxy, e observou a autorização de stop
remanescente se o Desktop fosse preservado ativo. Nenhuma resposta real nova
foi coletada; os exemplos usados são sentinelas sintéticas dos testes.
O bloqueador técnico foi aceito sob delegação, sem inferir incidente real.

Fonte corrigida: `7275c8ae9e7ccbadc6591cdbb051482ac76c3f3bb52a4f4b86f2966b2261c19e`.
Info/version agora descartam bruto, mantendo só exit/tamanho/hash e disposition
no manifesto; `daemon.json` conserva só as sete chaves públicas e `version.json`
só Version validada de Client/Server. Nenhum plugin/proxy completo é persistido.
Raw antes de validação continua para CID/imagem/inventários/efeitos públicos,
sempre local-only até o exportador futuro. Autorização de stop é zerada em
finally, mesmo quando o caminho herdado apenas preserva o Desktop ativo.
Três regressões falharam antes da correção (3failed/36deselected em0,63s):
info com proxy sintético, version com plugin sintético e stop não consumido.
A exceção de reconciliação no restore deverá ser tratada pela entrada como
HELD com categoria fechada, sem stop nem alegação de interrupção do runner.

Coordenador corrigido aceito pelo Claude2 na rerevisão10847, sessão51ea0d85,
sem bloqueador no escopo isolado.39passed em12,98s, Ruff/format324 e mypy
strict311/314323 limpos. Nenhuma execução nativa nesta rerevisão.
Sem commit/push/job/outro escritor. Gateway indisponível; B1/B2/D090/C1,
worker/SQL/aceitação IDE/MCP/Admin e produção continuam abertos.
