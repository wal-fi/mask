# Posse do leitor PG16 para cleanup — desenho antes do código

2026-10-30 sob delegação. Perfil8906e846 aceito28829, owner d671 e reader efe6
preservados. Incremento proposto: somente adapter puro de identidade e fakes,
sem CLI, start, kill, rm, ticket/release, observador de SO ou raiz operacional.

Novo pg16_shell_cleanup_policy.py captura por hash o perfil8906e846 e suas
definições já revisadas. Nenhum arquivo vivo é relido durante identity.
API: identity(info, task=32hex, case=str de enum fechado, command=tuple exata,
cid=64hex), com current inspect e CID capturado do create fornecidos pelo
coordenador confiável. Isso não é atestação do SO nem autoridade de remoção.

Reconstituir somente campos de posse pelo _capture do perfil capturado:
nome próprio task/case, Cmd wrapper exato, três labels task/sourceSHA completo/
manifest8676 e imagemcf78. command deve ser igual ao wrapper público construído
dessas mesmas definições. Sem aceitar um hash arbitrário fornecido pelo caller,
sem escolher identidade a partir do CID/nome retornados por inspect alheio.

Reutilizar identity do perfil, como adapter f1d9 anterior: objeto Intent
LOCAL via object.__new__, sem image admitida/Env, não devolvido nem fornecido
a create_args/validate_container/start. A identidade só lê campos reconstituídos
e o CID capturado. Posse é independente de aceitação: Env/limites/stdin ruins
não impedem cleanup próprio. OCI/labels extras não afastam os três próprios;
alteração de label próprio/Cmd/entry/imagem/nome/CID recusa.

Comparar resultado com cid capturado; erro de input/perfil/shape/vazamento
operacional de parser vira RuntimeError fechado PG16_READER_OWNERSHIP,
levantado fora de except, sem causa/contexto ou str/repr de entrada/erro.
Falha no hash da fonte capturada é PG16_READER_SOURCE. Não absorver
interrupção/cancelamento para inventar sucesso. Nunca consultar imagem,
resolver DNS ou chamar shell/Docker no adapter.

Fakes antes de qualquer consumidor:23casos válidos; perfil recusado mas posse
válida; troca entrecasos/task/CID/Cmd/labels/imagem/entry/nome; tipos inválidos,
prefixo de sonda antiga, segredo-canário em Env/mensagem sem vazamento,
erro __eq__ hostil fechado, sem reread em identity, sem Popen/write/mkdir.

O consumidor posterior ainda precisa provar inspect atual por ID, decidir
volumes com baseline completa local-only e persistir decisão antes de rm(-v),
recolher CLI/pumps/handles, ticket, ausência posterior e release. Watchdog
novo não receberá owner/loop, seed ou ticket; ainda ausente. Nenhum novo
exportador ou gate de publicação bruta neste adapter. Fontes consumidas
anteriores intactas; DesktopOff, Gateway indisponível, gates abertos.

## Precisões99525 incorporadas antes do código

Claude2 aceitou o incremento puro: case deve ser exatamente str, convertido
no enum do R do perfil capturado; tuple/Cmd com dois str exatos antes de
comparar; Intent local preenchido com os oito campos reconstruídos, nunca
command do caller. Comparados de info devem ter tipos JSON exatos, inclusive
listas/strings e labels próprios, recusando __eq__ que sempre retorna True
ou levanta erro. Não exigir Env/aceitação. Falha de captura/exec aninhado
deve mapear SOURCE fora do except; hash capturado rechecado em memória a
cada identity, sem reler arquivo vivo. Interrupção continua propagada.
