# PG16 público — projeção de evidência e preparo, antes de efeitos

2026-10-30, sob delegação. Entrada a6089275 e host7275 aceitos. Este incremento
não inicia Docker nem cria laboratório operacional. Fontes consumidas intactas.

## Exportador

Optar por **projeção**, não cópia dos arquivos de origem: todo bruto e toda
baseline completa continuam local-only, inclusive CID/image inspect. O resultado
publicável terá apenas summary.json e transport.json derivados, com schema
fechado de fatos públicos, hashes/tamanhos e categorias. Isso é mais conservador
que publicar raw aprovado pelo S1; não é DLP nem chamador de SQL/segredo.
Nenhum local-* será copiado, mesmo se vazio ou aparentemente público.

Admissão da raiz/destino por nomes fechados; arquivos regulares não-reparse,
lista fechada de nomes/tetos, snapshot limitado, JSON sem duplicatas/NaN.
Somente estado FINISHED/ABORTED e exit0/1 coerentes, nunca HELD/FRESH/INVOKED.
Pins/task/image/medida da entrada exatos. Recursos/restauração/thread devem
estar comprovados no resultado antes de publicar. Arquivos de origem são
rechecados antes de mkdir; falha deixa destino inexistente ou parcial não
declarado completo, sem apagar, sobrescrever ou repetir automaticamente.

Associar replies locais ao manifesto de CLI por tamanho/hash/exit e aos
labels fechados do ledger de comandos. Somente respostas registradas entram
em fatos derivados. Readmitir a imagem e a identidade do CID nos próprios
parsers pinados. Recalcular os fatos do probe a partir da saída local inteira,
exigir igualdade com o relatório estruturado e manter raw retido. Uma recusa
de perfil pode aparecer como categoria fechada, nunca como sucesso do ensaio.

Volumes: comparar conjuntos completos em memória. Resumo publica somente
contagens/digests canônicos e deltas. Schema de volume-baseline/decision/final
é fechado; decisões devem concordar com Mounts de inspect do próprio CID e
baseline local, e finais com inventários efetivamente capturados. Nomes em
claro só anônimos novos64hex comprovados no próprio CID, jamais preexistentes
ou globais. Hash é coerência de metadado, não sigilo nem prova de posse.

Diagnóstico por pares categoria/origem já fechados na entrada; não copiar
mensagens ou campos arbitrários de metadata. summary é construído de escalares
validados, não uma versão dos mesmos dicionários com algumas chaves removidas.
Manifesto lista os arquivos de origem por nomes fechados/tamanho/hash e motivo
de retenção; nenhum conteúdo raw. Fontes públicas oficiais não equivalem a
configuração de daemon publicável; info/version brutos seguem descartados.

## Preparador

Variante explícita do preparador8e024 sem mudar/invocar o original. Fixa o
pin da entrada a608, compõe o estado fechado FRESH e calcula o blueprint sem
imagem/daemon. command_for somente valida raiz/launcher pinado e devolve argv
python -I -B entry root. materialize cria apenas diretório novo e attempt.json
xb/flush/fsync; não chama entry.prepare/drive, processo, clock, Desktop ou Docker.
Não reutiliza nome/raiz/tentativa anteriores. Proposta concreta e sua revisão
continuam necessárias antes de materializar a raiz de laboratório real.

Testes com fakes/arquivos públicos pequenos antes de efeitos: terminal/HELD,
vazamento por alias/local-baseline, adulteração de manifest/pins/task/cid,
volume preexistente/unknown, nomes/hash sem coerência, fonte alterada, destino
existente, limites/duplicatas/symlink policy, falha de escrita e não-invocação.
Não fecha B1/B2/D090/C1, SQL, serviço, IDE/MCP/Admin ou produção.

## Precisões55166 e schema antes da implementação

Preparador02d1/direção aceitos pelo Claude2 (55166). Hash de baseline/replies
de volumes é coerência, não sigilo de nomes previsíveis. Recusa de perfil é
fato fechado e mantém NOT_PASSED; somente recurso comprovado permite exportar.

Schema exato de summary.json (nenhuma chave extra copiada da origem):

| Campo | Conteúdo fechado |
|---|---|
| kind | MASKGW_PG16_PUBLIC_SUMMARY_V1 |
| task, entry_sha256, host_sha256 | Identidades/pins validados |
| reported_exit, outcome | 0/1 e PG16_PUBLIC_VERIFIED/NOT_PASSED coerentes |
| resources | owned_cleanup, inventory_restored, volumes_restored booleanos |
| cycle | checkpoint_count, head, interval_a_b_ms, boot_equal, replayed |
| commands | Lista de label fechado, exit inteiro, bytes inteiro e sha256 |
| image | id, admitted, category, pg_version, oci_labels_present, oci_label_count |
| cid | CID próprio64hex ou null antes de create |
| profile_observations | index/sha256/bytes/cid/accepted/category/groups/state |
| post_execution_state | Running/Pid/OOMKilled/Dead/ExitCode ou null sem report |
| probe | Fatos recalculados pelo parser pinado e iguais ao relatório, ou null |
| owner | phase/fault/seed_delivery/released/role/cid fechado, ou null sem case final |
| volumes | status/initial_count/initial_sha256/final_count/final_sha256/decisions/finals |
| watchdog | fired/held/thread_joined booleanos |
| desktop | initial_active/state/restored validados |
| diagnostics | failure/cleanup/restore pares category/origin fechados |

groups contém identity/config/profile/surface/mounts: true só com aceitação
completa pelo parser, false no grupo da recusa conhecida, null nos demais
sem atestação independente. Não duplicar predicados do perfil para inventar
prova separada. Estado pós-execução vem do último own-inspect capturado após
report; antes de executar não é confundido com parada após execução.

Ciclo usa replay dos arquivos imutáveis: A→B somente com os12 checkpoints,
boot igual e intervalo calculado dos samples; tentativa abortada antes de B
deixa intervalo null. A lista de comandos publica somente labels fechados
do fluxo, exit/tamanho/hash. Campos arbitrários e mensagens são descartados.
Owner só tem phase/fault quando há case final persistido; ausência em tentativa
abortada é null, não fase inventada. Watchdog held não é prova de release.

Em abort antes de admitir volumes, sem nenhum CID/intent de create confirmado,
volumes.status=NOT_ADMITTED e contagens/digests null; não dizer que inventário
foi restaurado ou que estava vazio. Somente exit1 pode usar esse caso. Depois
da adoção da baseline, exigir RESTORED e reconciliação dos conjuntos capturados.
Normal exit0 exige report, owner CLOSED, estado final saudável, imagem e perfil
aceitos, journal completo e todas as provas de recurso/restauração/join.
