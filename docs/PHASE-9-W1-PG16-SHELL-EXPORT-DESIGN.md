# Exportador público do leitor PG16 — desenho e notas de validação

2026-10-31, sob delegação vigente. Incremento só de código/fakes: novo
`docs/poc/pg16_shell_export.py` e `tests/test_pg16_shell_export.py`. Nenhum
Docker/PG/shell/worker/SQL/segredo, raiz operacional, preparador, comando ou
rodada. Entrada afaffad0, Host 8c41605f, exportador antigo 95f0 e a task de
pins 3eb3 ficam intactos. Envelope 47012 continua só planejamento.

## Fonte e carga

Captura somente a entrada afaffad0 por SHA e executa definições; a partir
dela carrega por pin o perfil 8906, entrega 42f7, policy 96e8, volumes 6e38,
watchdog cf66, core e o vocabulário fechado da própria entrada (bytes fixados
de 4bc/LIBRARIES/SOURCES, sem construir Host). Não chama prepare/admit/run/
drive/main nem o exportador antigo. O estado esperado é reconstruído com o
mesmo esquema de `admit` (kind, task, phase, invoked, SHAs, pins, transitivos,
stdlib, imagem, 23 medidas de create e plano de entrega) e comparado byte a
byte com `attempt.json`; não depende do preparador ainda inexistente.

## Snapshot e limites

Raiz `Temp/maskgw-pg16-shell-reader-v1-<32hex>` mais até 23 diretórios
`watch-NN`, uma profundidade. Nomes fechados; case/índice conferidos contra
CASES; sem symlink/reparse/desconhecido. Limites: 1024 entradas, 4 MiB por
arquivo, 32 MiB no total, 512 comandos; as mesmas checagens repetem antes da
primeira escrita. Saída: só `summary.json` e `transport.json` novos.

## Provas exigidas

- Terminal FINISHED/ABORTED coerente com exit 0/1 e outcome; nunca HELD;
  `terminal_resources_verified` e `desktop_restored` verdadeiros. Sucesso
  exige os demais recursos, journal 12/head/cycle, 23 casos, 4 positivos e
  19 negativos, history vazio, cleanup_attempts 1.
- Ledger: cada linha `commands` com chaves fechadas, sem exit nulo; cada CLI
  ligada à linha do manifesto por label/índice crescente/exit/bytes/SHA e ao
  artefato local por nome/tamanho/hash; version/info descartados.
- Caso completo: bloco contíguo exato volumes-before/create/inspect/
  inspect-result/inspect-cleanup/[kill/inspect]/rm/absent-after seguido de
  volumes-final restaurado. Create e rm devolvem o CID do record; ausência
  vazia. Todo inspect exit 0 passa a identity da policy; o pós-create e o
  inspect-result passam validate_container. Relatório reparseado pelo leitor
  pinado com o returncode registrado, que deve ser 0 ou 42 conforme o vetor;
  categoria negativa nunca vira sucesso. Inspect-result ligado a label/índice/
  artefato, State parado/Pid0/sem OOM/sem Dead/ExitCode igual ao returncode.
- Owner CLOSED/released/fault nulo/`seed_delivery` SENT, que aqui significa só
  handoff local do vetor público; nunca seed privado nem recepção. Plano de
  entrega igual ao `delivery_for`.
- Records em ordem, intent inicial byte a byte, CIDs únicos. Caso incompleto
  final só em ABORTED: create único e última ação absent-after vazia, ou
  `create_not_invoked` sem CID. Relatório parcial só se reparse confirmar.
- Watchdogs: diretórios contíguos, NOT_STARTED/JOINED fechados, iniciados
  joined/sem held/sem fire; última evidência `monitor-case-*` igual ao
  resultado; earlier HELD/erros reportados e proibidos no sucesso. Qualquer
  fire, evidência de emergência ou supervisão incerta é recusado.
- Volumes: baseline local completa igual ao volumes-initial e primeira
  metadata; volumes-before iguais. Cronologia ligada ao ledger: cada `rm-C`
  exige uma decisão daquele CID imediatamente antes dele na sequência de
  metadata, recalculada dos Mounts do ÚLTIMO inspect próprio anterior a esse
  rm; cada volumes-final exit 0 exige o final seguinte, recalculado do
  inventário bruto com linked da última decisão por CID até ali. Decisão
  atrasada, duplicada ou de outro CID é recusada; só em ABORTED uma decisão
  cujo rm não rodou é aceita se a mesma CID tiver decisão posterior.
  Último final restaurado. Nunca só por flag ou hash.
- Comparações de prova são tipadas/canônicas (False não é 0): plano de
  entrega, monitor do caso, índice/artefato/exit do inspect e contadores do
  owner.
- Diagnósticos: histórico inteiro preservado, origem/categoria no vocabulário
  fechado da entrada; `deadline` só com RESTORE_MARGIN/POST_B_OVERRUN.

## Escrita

Toda leitura é limitada: `open rb` + `read(limite+1)`; arquivo que cresceu ou
passou do limite é recusado sem ler o resto. A raiz e TODOS os ancestrais, e
o pai do destino e TODOS os seus ancestrais, precisam ser diretórios reais,
sem link ou reparse point; a checagem ocorre antes das leituras, de novo
antes do `mkdir` e, para o destino criado, antes do rename. Antes da primeira
escrita relê com limite todos os fontes públicos capturados (entrada, host,
7275, V2, 4bc, LIBRARIES, SOURCES e transitivos; nenhuma configuração ou
binário nesta etapa pura) e o snapshot completo. Grava `summary.json` e
`transport.json.next` com xb/contagem exata/flush/fsync, confere a lista do
diretório e relê os dois. O rename para `transport.json` é a ÚLTIMA operação:
depois dele nada falível roda e a função retorna; `transport.json` visível
sempre significa exportação completa e relida. Falha antes disso não apaga,
não sobrescreve, não repete e nunca deixa `transport.json`. Erros saem como
`ExportError` com código fechado, fora de except, sem causa/contexto.

## Schema publicado

`summary.json` (`MASKGW_PG16_SHELL_READER_SUMMARY_V1`): task, SHAs de entrada/
host, reported_exit, phase, outcome, a_entered, resources (booleano, ou null
quando o campo não foi observado, por exemplo owned_cleanup no pré-A), desktop,
cycle (contagem/head/intervalo/boot/rejeição), commands (posição/label/exit/
bytes/sha256/seconds), image (id/admitida/versão/contagem de labels), counts,
cases, watchdogs, volumes (contagens/hashes/decisões/finais) e diagnostics.
`transport.json` (`MASKGW_PG16_SHELL_READER_TRANSPORT_V1`): fonte com nome/
bytes/SHA/published=false/motivo LOCAL_ONLY ou PROJECTION_ONLY, diretórios,
artefato derivado e `source_unchanged`. Nenhum raw, caminho, ambiente,
configuração, nome de volume preexistente ou mensagem original.

## Limitações declaradas

Lote com qualquer fire de watchdog é recusado (projetor de evidência de
emergência fica para incremento próprio). Argumentos de `rm`/`rm -v` não são
registrados no ledger; a prova de volumes vem dos inventários. `seconds` de
cada comando é medido pelo host só DEPOIS dos pins daquele invoke e não
inclui hash de fontes/executáveis. O Host 8c não tem campo de duração por
owner nem por fsync: a primeira matriz mede conclusão/prazo B e os tempos de
CLI disponíveis, NÃO mede diretamente O nem w do envelope sem instrumentação
própria. Se um ancestral legítimo (por exemplo pasta redirecionada) for
reparse point, a exportação recusa fechada. Fakes geram a raiz pela entrada/
host aceitos com transportes falsos e adaptadores de metadata real; não são
medição nativa. Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.

## Revisão independente — achados medidos pelo revisor

Primeira entrega: fonte a7664f37, testes 4815e041; o revisor registrou 41/41
oficiais em 68,26s e, com hook próprio sobre a fixture real de sucesso, cinco
contraexemplos (registro do revisor, não execução do escritor):

1. P2 `regular()` conferia tamanho pelo lstat e depois `read_bytes()` sem
   limite; caminho falso com tamanho 1 devolvendo `xx` alocava antes de recusar.
2. P2 só raiz e pai de saída eram conferidos; `Temp` como diretório com
   reparse 0x400 e a exportação passava.
3. P2 trocar as posições da primeira decisão e do primeiro final de volume,
   mantendo bytes canônicos e sequência sem lacuna, era aceito.
4. P3 `hold_open` False trocado por 0 no primeiro caso era aceito por `==`.
5. P2 falha ao reler `transport.json` depois do rename dava EXPORT_IO com o
   marcador já visível.

Correções nesta revisão: leitura limitada; cadeia completa de diretórios;
cronologia por eventos do ledger; comparação tipada; nenhuma operação falível
depois do rename. Regressões formais adicionadas para os cinco, mais escrita
curta, ancestral do destino, raiz como link direto, decisão duplicada,
inspect_exit_code False e monitor com 1. Resultado das novas execuções fica
para a validação independente.
