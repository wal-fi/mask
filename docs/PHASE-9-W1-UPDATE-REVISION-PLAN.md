# W1 — revisão do próximo coordenador, antes de novo código/efeitos

2026-10-27, sob delegação. A tentativa1 falhou antes da instalação e seus
recursos foram restaurados. Não repetir o4bc0b083 nem modificar sua fonte,
o restore9d4fa8b9 ou os witnesses. Nenhuma nova tentativa é iniciada por este
documento. Este é um desenho para revisão depois da evidência da recuperação.

## Menor mudança funcional proposta

Um módulo novo, específico, usa4bc0b083 apenas como biblioteca hashada. Não
duplica o coordenador inteiro nem chama seu main. Fonte anterior e fakes
permanecem preservados. A nova entrada tem estado/programa/raiz próprios e
verifica tanto seu SHA quanto os seis helpers e o4bc0b083 em cada efeito.
O estado interno legado conserva o pin4bc0b083; o pin da nova entrada fica
separado e nunca é trocado temporariamente numa estrutura compartilhada.
Sem novo backend de comandos/configuração de produto.

### Labels de aceitação explícitos

- CID: conjunto exato dos3labels próprios task/source/manifest, fato medido
  na tentativa1. O validador original continua conferindo todo o perfil de
  segurança, comando e limites para aceitar cp/start. Nenhuma aceitação por
  ausência/valor opcional de label esperado.
- Imagem: continua com as4chaves de labels do contrato anterior. O commit
  acrescenta explicitamente `LABEL desktop.docker.io/ports.scheme=v2` como
  metadado público, além das mudanças USER/WORKDIR/ENTRY/CMD já aprovadas.
  Isso garante a construção desejada por declaração, sem presumir herança
  do label da imagem pelo container. Validar novamente Config inteiro e
 3layers+um; nenhuma normalização automática de outro campo.

### Posse e limpeza

Aceitar exige perfil completo e3labels exatos. Provar posse para cleanup usa
nome/CID (se conhecido)/imagem/3labels próprios e comando exato da intenção.
Labels de apresentação extras ou mudança de limite que causaram recusa de
aceitação não apagam a posse. Nenhum dado/contexto/credencial alheio é tocado.
Uma intenção de create ambíguo exige identidade completa e comando exato
antes de adotar CID; sem isso fica pendente. Kill só se próprio running,
com reinspeção, depois PID0/não-running, rm sem force e ausência por ID.
Não matar/apagar por nome parcial, label isolado ou imagem. Nenhum prune.
Rollback de tag continua por posse, não Config de aceitação, como B2 corrigido.

### Checkpoints imutáveis

Guardar cada estado aceito em arquivo novo, além do cycle.json corrente,
antes de retornar ao chamador e antes do próximo efeito. A, O1..O9, READY e
B dão12 checkpoints: amostra completa em anchor/last, fase, contagem, reason,
SHA e ordem. Repetição de write falha fechado; não sobrescrever o histórico.
Estado FAILED guarda último aceito e arquivo separado da amostra recusada,
como já existe. Um abort após B não duplica ou inventa checkpoint.
Replay host usa o mesmo núcleo puro sobre cada sample em ordem e confere
o estado retornado byte a byte; não inventa tempo/origem externa nem prova
de autenticidade fora do chamador confiável. B só atua após persistência.

## Gates seguintes

Revisão deste desenho antes do delta; testes com os3labels reais, rejeição
de outro perfil, cleanup por posse apesar de recusa de aceitação, comando
do commit explícito e Config da imagem inalterado fora do contrato. Fakes
de abort/boot/idade e journals12replayáveis/colisão de arquivo. Comparação
estrutural das partes herdadas congeladas. Código/fakes, depois estado e
comando de raiz nova, revisados antes de A. Sem retry da tentativa1, aumento
de limite, instalação, SQL/PG16/worker ou liberação de serviço por este desenho.
B-1/B-2/D-090/C1 e critérios de produto permanecem abertos.

## R1–R5 incorporados após revisão do desenho

Claude2 aceitou a recuperação como baseline. Direção do desenho aceita,
com cinco contratos fechados aqui **antes do código**:

- R1: os dois pontos de labels de CID no4bc são inspect_own (usado por
  create_own/run_own/perform_b/cleanup_owned) e watchdog/WATCHDOG_ID. Ambos
  serão tratados, nos CIDs install e probe. inspect_own usa posse comum
  (nome/ID se conhecido/imagem/3labels próprios/argv exato); aceitação soma
  perfil completo+conjunto exato3labels. Watchdog usa a mesma posse antes
  de kill, não o label de apresentação nem perfil de aceitação.
- R2: o valor público v2 será copiado do campo observado na base da tentativa1,
  ainda validado no preflight. Nenhuma afirmação sobre a semântica do Desktop.
  commit acrescenta esse LABEL explicitamente para manter o contrato exato
  de4labels da imagem e reutilizar validate_new_image7540 inalterado.
- R3: **evitar a duplicação de métodos grandes** por três pontos pequenos.
  start_cycle/checkpoint/perform_b permanecem os MESMOS objetos de função
  herdados do4bc. save grava ciclo corrente e acrescenta journal imutável
  antes de retornar (inclusive A, que já passa por save). cli acrescenta
  somente --change LABEL à lista específica commit-own, após conferir seu
  formato; não encaminha comando de usuário. inspect_own é a nova fronteira
  posse/aceitação. watchdog precisa ser copiado; comparação AST normalizada
  prova que só seu bloco de identidade foi substituído pela posse comum.
  Demais métodos herdados têm identidade de função conferida em teste.
  A nova entrada main/admissão é específica, sem chamar main histórico.
- R4: state.program_sha256 permanece4bc0b083 permanentemente; novo campo
  entry_sha256 admite o módulo novo. pins sobreposto primeiro chama o pin
  original e depois confere entry_sha256 no arquivo novo; nenhum campo é
  trocado temporariamente, nem em outro thread. Ambas fontes serão conferidas
  antes de cada efeito; create_measurements usa a task nova.
- R5: journal de12arquivos xb ordenados, cada um com ação START/OBSERVE/READY/B,
  sample completo, encode do estado e SHA do checkpoint anterior (zeros no
  primeiro). save só registra estados aceitos diferentes do último encode;
  abort pós-B não inventa outro checkpoint. FAILED/ABORTED não vira aceite.
  rejected-sample também gera arquivo xb próprio com ação/sample/estado
  recusado e link ao último checkpoint. Replay usa start e advance do mesmo
  core, compara ACCEPT e encode byte a byte e verifica a cadeia/ordem. Validar
  os12 do disco após start_cycle e antes de perform_b. Falha de escrita/replay
  impede create, não é só observabilidade.

Os hooks são métodos fechados do coordenador, não callbacks fornecidos pelo
usuário. Esta precisão de R3 segue para revisão antes da implementação.
Nenhum fonte consumido foi editado, nenhum efeito Docker/clock novo.

Precisão R3 aceita pelo Claude2 antes do código, sem bloqueador de desenho.
Cinco métodos sobrepostos exatos:save/cli/inspect_own/watchdog/pins; a função
comum de posse fica no módulo e o construtor é herdado. Posse tolera labels
extras; aceitação exige3exatos em toda inspeção normal, install/probe.
cli só transforma commit-own de formato exato e grava a lista final;
outras listas são encaminhadas sem alteração. Transição do journal é
validada por regra fechada+replay, não apenas inferida livremente da fase.
Todos os outros métodos mantêm identidade de função. Rerevisão de código,
testes e estado/comando continua necessária antes de quaisquer efeitos.
