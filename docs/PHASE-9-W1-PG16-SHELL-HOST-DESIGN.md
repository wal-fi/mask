# Composição pública do leitor PG16 — desenho antes de código e efeitos

2026-10-30, escolha técnica sob delegação. Checkpoint a59da63 publicado,
reader/owner/perfil/posse/watchdog aceitos. Nenhuma nova raiz, DockerCLI,
thread, processo do ensaio, seed privado, cluster, SQL ou alteração da Oracle.
Este desenho fecha primeiro a política de entrega; depois o host inteiro terá
revisão própria. Não executar fontes/root/script consumidos de rodadas antigas.

## 1. Política de entrega pública, incremento mínimo separado

Novo pg16_shell_delivery.py captura owner d671 por hash, que já captura reader
efe6 e canal e6ca. PublicDeliveryOwner é subclasse explícita de PublicReaderOwner,
com **somente __init__ sobrescrito**. Sem monkeypatch/AST/globals alterados;
start/adopt/feed/send_vector/pump/drain/quiesce/ticket/close/handle são os
mesmos objetos. Não aceita Seed/corpo/comando/bytes do operador.

Entrada(task32hex,cid64hex,case=str exata entre23valores) converte case no enum
do reader capturado. Só tipos primitivos cruzam namespaces; não coagir enum ou
subclasse str. Após construir o owner original, troca o Vector congelado por
dataclasses.replace apenas quando fault é HEADER, pela regra fixa abaixo.
Não muda o wrapper, CORE_SHA, parser, resultado esperado ou fonte original.

- Nove casos HEADER: magic/role/digit/headerNUL/interiorNUL/CR/zero/oversize/
  short-header. Enviar somente wire[:16], ou15 no short-header, em um chunk,
  e fechar stdin pelo método herdado. Mode HEADER_PREFIX.
- Outros14 casos: wire/chunks/hold_open **exatamente** do Vector original.
  Mode EXACT_VECTOR. Inclui corpo16KiB com NUL/trailer interior, fragmentação
  fixa0,02s, RETAIN e WAIT_* com stdin aberto, corpos/trailers parciais e
  sobra ASCII/NUL/LF. Nenhum byte novo ou normalização de frame.

Registro público congelado de entrega: case/mode/wire_bytes/chunk_sizes/
hold_open, somente descrição da configuração; não é contagem medida de
syscalls ou prova de recepção. Metadata de SENT continua handoff local.
BrokenPipe/erro de close/pump/timeout é reprovação, mesmo com fault esperado.
Não há exceção para ignorar I/O. Oráculos e prazos12s/8s/1s inalterados.

O perfil8906 referencia o owner-base d671, efetivamente herdado. O novo
deliverySHA será pinado separadamente no host/estado/evidência, sem reescrever
retroativamente manifesto/perfil. Antes de start, host confere Target CID/
task/imagem/core, wrapper e SHA iguais aos do Intent do perfil8906. Não alegar
que o label do perfil sozinho autentica todo o código do host.

Gates puros:23casos, contagem9/14, bytes/chunks exatos, HEADER truncado sem
corpo e oráculo preservado pelo decoder autoritativo, todos métodos herdados
idênticos exceto constructor, sem input privado/arbitrário e sem efeitos no
import. Fakes de envio/EOF/RETAIN/BrokenPipe usam o canal original, sem Docker.

## 2. Host público específico, contrato para revisão posterior

Novo pg16_shell_host.py como variante explícita das definições host7275 e
V2b593/4bc; sem chamar entry/main antigos ou editar fontes congeladas.
Nenhum caminho de install/cp/commit/run_own genérico/watchdog antigo pode
ficar disponível. CLI fechada a version/info/ps/imageinspect/volume-ls/create
de blueprint exato/inspect próprio/kill próprio/rm(+v)/desktopstop; start
interativo somente pelo owner. Nunca stdin/SQL ou segredo em argv/ENV.

Matriz proposta fixa:23casos na ordem do enum efe6; sem seleção dinâmica ou
retry. B terá300s globais, definidos antes de efeitos (90s da sonda anterior
não é promessa herdada para23containers). Limites12s de owner/8s shell não
se ampliam. Watchdog continua600s desde **mesmo Bstart global**. B300 é teto
de supervisão para duração típica, não soma de piores casos dos23casos. Margem
conservadora com um join bloqueante dentro de B:300+55+31+93+55=534s<600,
sem teto absoluto do SO. O erro de orçamento reprova, sem retry/ampliação.

Um único CID vivo/pendente por vez. Antes de próximo caso: owner quiesced e
reaped, ticket, inspect/posse/stop/rm/ausência posteriores, volumes iguais à
baseline, owner released e watchdog joined/nofire. Qualquer fired, create
ambíguo, CLI/pump/handle incerto ou falha de persistência aborta o lote todo;
não criar próximo CID. Stores/Watchdogs dos23casos serão construídos antes de
A, sem threads, em diretórios próprios. No checkpoint B todos recebem uma
única vez arm_b(globalBstart); em cada ativação pulse(now) antes do start.
Store nunca recebe None/troca de caso após primeiro snapshot. check_snapshot
precede publish; birth só adicionado/confirmado pelo handle original dc248.

Preflight readmite imagemcf78 e perfil antes de input; root/digest/pins próprios.
Inventário inicial de volumes completo local-only, antes de cada create nova
listagem igual/recente≤30s e intent durável antes de uma única chamada create.
Não reaproveitar a idade do início da matriz sem nova observação/listagem.
Create de cada caso só pode ser o blueprint planejado antes de A. Metadata
info/version bruta continua descartada; inspect/listagens ficam local-only
antes de parser, com ledger/manifest tipados e categorias fechadas.

Registro de caso deve conter returncode CLI real, stdout_bytes total,
report_bytes, política de entrega, relatório recalculado usando esse mesmo
returncode, e rótulo do inspect pós-execução. Exigir State parado/Pid0/semOOM/
semDead e ExitCode **igual ao returncode** (0 ou42). Não converter42 em0
nem confundir falha DEADLINE do host com fault=DEADLINE esperado do shell.
Sem prefixo de sucesso após I/O. Raw não é publicado diretamente.

Cleanup serializa com o watchdog. Decisão de volumes durável antes de rm-v,
sem apagar named/preexistente ou usar prune/force. Mesmo já ausente, conferir
volumes. Tokens de kill/rm/desktopstop de uso único. Último conjunto de CIDs e
volumes igual ao inicial, todos owners/threads/CLIs recolhidos antes de stop.
HELD mantém o mesmo processo/loop; não fechar loop com tarefa viva nem iniciar
escritor/limpeza paralela improvisada. Todos monitores anteriores retidos no
registro; sucesso não olha só o último. Watchdog fired sempre reprova o lote.

## 3. Sequência e limites

### Precisões da composição para revisão do host

- Delivery42f7e647 foi aceito42864; piná-lo além dos hashes8906/96e8/cf6634da.
  O host usa C/Target/Absent do namespace da entrega para seus owners e usa
  Image/Case do namespace do perfil somente naquele perfil. Entre eles só
  cruzam task/case strings, CID, wrapper, SHA, contagens e bytes do relatório.
- Implementação proposta é variante fonte explícita do host7275, com herança
  somente de definições V2b593/4bc. Não inicializar o host antigo e trocar
  seu namespace depois. Preflight usa parser base profile.P.one; o case do
  Intent é convertido apenas pelo enum próprio do perfil.
- Lista fechada dos23cases vem da ordem efe6, sem parâmetro de seleção do
  operador. Antes de A, gerar todos os blueprints e medidas. Cada create tem
  token consumido antes do await, intent xb/fsync, record próprio e no retry.
  Intents/owners/births/monitores são mapas por case; o CLI admite kill/rm
  somente com token próprio CID/args de uso único. Nunca derivar o Intent de
  cleanup do case atualmente selecionado; usar o do próprio record.
- Todos Stores/Watchdogs existem antes de A, ainda sem Snapshot/baseline/CID,
  com Store(now_preA). Bstart é gravado e armado em todos uma vez no checkpoint
  B. Antes de ativar cada thread seguinte, pulse(now), sem novo constructor.
  Publicar primeiro Snapshot somente após baseline válida. Snapshot nunca
  recebe None depois disso. Callback fecha sobre case/monitor específico,
  agenda no loop principal e cancela só o foreground daquele case; não dar
  ack em monitor diferente. Callback antigo não autoriza próximo caso.
- Um heartbeat local por Store; primeiro monitor.close/join, depois parar/
  aguardar heartbeat, registrar metadata e só então ativar Store seguinte.
  Não repontar um heartbeat ainda vivo para o Store seguinte. Após join,
  revalidar fired/held e registrar metadata do monitor; todos são retidos.
  Entre casos só há intervalo sem supervisor quando nenhum recurso está
  vivo/pendente e o último join foi positivo; antes do próximo create o
  supervisor novo já deve estar ativo. Se fired, nenhum próximo create.
- Antes de cada create, nova listagem de volumes igual à baseline global;
  timestamp da observação nova determina a idade≤30s, sem renovar baseline
  por atribuição arbitrária. Baseline privada e fonte da evidência mantidas.
- Expected negativo é resultado verificado apenas quando parse_report aceita
  exatamente fault/exit42 e inspect confirma o mesmo42 sem OOM/Dead. Nenhuma
  falha de IO/close/deadline do host vira esse resultado. Owner registrado
  antes de start e Birth capturado síncrono em finally, inclusive spawn tardio.
- _collect aplica quiesce até2x3s, mutex1s, cleanup25s, decisão durável antes
  de kill/rm, ausência posterior ligada ao ticket e volumes iguais. Case só
  é finalizado depois de release+join positivos. Sucesso global exige23casos
  finalizados, todos monitores joined/nofire/noheld, commands sem exitNone,
  CIDs/volumes restaurados e fontes/clock/boot/Desktop confirmados pela entrada.
- Gate de CLI e teardown precisam de fakes antes de main/entry: create repetido
  ou de outro blueprint, preflight incompleto, body/Case trocado, record/CID
  alheio, callback obsoleto, fired no último join, falha de persistência, CLI
  não recolhido, cancelamento em cada fase, prefixo+IO, exit42 divergente,
  next-case antes de release/join, restore sem todos os monitores positivos.
  Gate estático compara os métodos realmente preservados; diferenças do
  host7275 serão declaradas. Sem ROOT/main/CLI real nesse incremento de código.

Revisão do incremento1→código/fakes/revisão. Depois revisão específica do
host e sua matriz de concorrência/cancelamento/falhas, implementação/testes;
depois entry com HELD/diagnóstico, exportador por projeção sem raw, preparador/
proposta/script/pins e revisão antes de **uma** rodada nativa. Aceitar este
desenho não executa o host nem autoriza antecipar qualquer efeito real.

Nenhum initdb/servidor/SQL/credencial/worker/Gateway neste ensaio do leitor.
Perfil Oracle621 não muda; B1 fim a fim/B2/D090gate2/C1/SQL/produção abertos.

## Precisões33095 para o incremento1, antes do código

Claude2 aceitou apenas entrega/fakes; seção2 ainda precisa de revisão própria.
Testes devem provar igualdade literal do prefixo e ordem de leitura do núcleo,
não usar decoder Python como prova de shell real. dataclasses.replace altera
somente wire/chunks; short-header continua15bytes originais, mesmo modePREFIX.
Case é str exata do namespace próprio; erro fechado fora de except. Subclasse
tem só __init__ além de metadados de classe, todos demais atributos/métodos
resolvidos são os mesmos objetos. Case/Vector/Target de outros namespaces
não cruzam: o host compara só primitivos e SHA/bytes. Nenhum input privado.

Nota para próxima revisão do host: B300 é fail-closed, mas o orçamento deve
considerar os23 casos,3WAIT com8s e rm já observado até6,3s. Antes da rodada,
justificar ou recalibrar B, sem ampliar owner12s/shell8s e sem adaptação depois
de uma falha. Margem534<600 inclui um join que bloqueie o event loop dentro
de B; é aritmética de supervisão, não medição do SO.

## Precisões2192 incorporadas antes do host

1. Artefatos main case-NN-<case>-intent/report e local-case-NN-<case>-output;
   cada watchdog recebe watch-NN/ próprio, mkdir novo antes de A. Índices/cases
   vêm da ordem fechada. Exportador futuro deve conhecer esses23 diretórios e
   recusar reparse/symlink; não usar95f0 flat sobre esse layout.
2. Create de caso i exige todos os i anteriores removidos/ownerreleased/
   monjoined/nofire, record atual persistido, token ainda não consumido e B
   dentro do prazo. Normal CLI e start do owner rechecados antes do efeito;
   não depender só do callback de asyncio.timeout após um join bloqueante.
   Inspect/kill/rm somente CID ativo ou pendente não removido em cleanup;
   removido só admite ps --filter id=. Tokens exatos e de uso único.
3. Intent/owner/birth são escolhidos sempre pelo case do próprio record,
   nunca por _intent/currentCase. A policy96 recebe case. Owner da entrega
   fica registrado antes de start e wrapper/Target comparados por primitivos.
4. Não existe publish(None) no host novo. Fechar monitor encerra seu caso.
5. Ordem: monitor.close/join→parar/aguardar heartbeat local→metadata
   joined/nofire/noheld→ativar próximo monitor/heartbeat→check_snapshot/publish.
   Qualquer falha aborta sem próximo caso. Cleanup final deve continuar
   tentando recolhimento próprio; fired reprova o ensaio, não impede restauração
   segura quando todos recursos/threads/inventários/boot foram comprovados.
6. Construir23Stores/Watchdogs antes de A, na thread principal, em diretórios
   próprios, sem iniciar threads. Cada captura/exec aninhado ocorre só nessa
   preparação; não23vezes durante B. Só o primeiro monitor inicia antes de A.
   Monitores ainda não iniciados são NOT_STARTED, nunca chamados de joined;
   sucesso23casos exige todos iniciados e joined, aborto exige coleta positiva
   de cada thread que tenha sido iniciada/tentada, sem inventar prova.
7. Callback referencia o próprio monitor/case; pins normais rejeitam fired
   de qualquer monitor atual/anterior. Cleanup usa pins(cleanup=True), como
   o caminho de restauração4bc. Desktopstop exige todos monitores iniciados
   joined e toda posse/volume/CLI positiva; nofire é exigido para sucesso,
   não usado para deixar recursos próprios vivos após uma falha recolhida.
8. Parse usa observation.returncode real; State exigido parado/Pid0/semOOM/
   semDead/ExitCode exatamente igual,0ou42. IO/prefixo nunca gera sucesso.

### Insumos medidos para orçamento, sem extrapolação de garantia

Fonte pública já filtrada: oracle9-t4-v2-run-20261029-42d363a11156/result.json.
Nos sete casos: create0,266–0,328s, inspect0,109–0,141s, rm0,125–0,141s,
ausência0,094–0,140s. Essas durações são do controle T4Oracle, não da imagem
PG/reader; owner attach/drain não consta como duração desses comandos.
PG público summary81e72756 não inclui seconds, portanto não inventar tempos
dele nem ler seus brutos Temp sem novo filtro. A observação histórica de
rm6,3s citada na revisão não é substituída pela amostra rápida T4. Os3WAIT
somam pelo menos24s de shell e cada owner pode custar12s; máximos de cada
etapa não cabem emB300 para23casos. O limite será revisto/justificado antes
da rodada com esses limites explícitos; se mantido e excedido, NOT_PASSED.
Nenhuma fonte/limite/rodada será alterada depois para converter falha em passe.
