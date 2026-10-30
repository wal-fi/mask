# PG16 público — identidade para a limpeza, incremento isolado

2026-10-29, sob delegação. Direção6796, perfilfe2f8ba8 e ownera02f0b71 aceitos;
nenhum novo efeito real, DockerCLI, processo de laboratório, PG/SQL ou seed.

`docs/poc/pg16_public_cleanup_policy.py`, SHA-256
`f1d94928112afc6a2c0f179201cab74e60dd515c94337e625e1ea8912d28a46c`.
Captura perfilfe2f por hash/arquivo regular, sem reparse; identidade depois
usa só memória/captura validada, nunca imagem/env/arquivo vivo. Task e comando
exatos da fonte pública fixa. Reconstitui objeto **local** somente para o
identity autoritativo pinado; não executa construtor de create, não expõe
objeto incompleto, não aceita backend/comando arbitrário. O campo imageNone
não é admissão de imagem, é desnecessário no método de cleanup pinado.

CID esperado é parâmetro obrigatório do registro de create, nunca inferido
do inspect. Nome/imagem/entry/argv e três labels próprias iguais; metadados
extras podem reprovar aceitação sem bloquear identidade para remoção própria.
Nenhuma CLI, remoção, prova de ausência, ticket ou release neste adaptador.
Somente retorna CID quando coincide; o supervisor ainda deve provar origem
do registro e sequência causal de quiesce/inspect/remoção/ausência.

25 testes do adaptador; seleção relacionada canal/owner/perfil/volumes/adapter
teve rodadaA **249passed/1failed/1deselected em8,03s**: teste antigo
`test_pending_spawn_is_not_cancelled_and_has_no_ticket_or_release`, na
assertiva de ticket após recolhimento. Fonte e6ca e teste94a127be intactos;
teste usa CLOSE_SECONDS=0,01, mas a causa do evento é **indeterminada**.
Isolado1passed/76deselected0,21s; repetição integral B, sem mudar código,
tetos ou seleção: **250passed/1deselected em7,71s**. RodadaA permanece reprovada,
não atribuída ao host/load por suposição. Não é estabilidade comprovada.

O único deselect é prova nativa de PipeHandle consumida anteriormente,
excluída explicitamente desde a seleçãoA, sem apagar a falha do caso antigo.
Novos componentes só fakes. Ruff src/tests limpo, format324, mypy strict311/
314 em320arquivos limpos, runtime só Windows3113. Helpers com lint restrito.
Sem suíte integral PG/frontend/pacote neste incremento de laboratório.

Adapter aceito isoladamente pelo Claude2 (5979), sem bloqueador; confirmou
o tratamento da falha temporal conhecida sem atribuição/estabilidade inventada.
Origem durável do CID/comando e um adaptador único no main/watch/emergency
continuam obrigações de integração, não fatos já medidos. Watchdog/emergency PG,
host/CLI fakes e evidência, comando/raiz novos e rodada real ainda faltam.
Não reutilizar loggers públicos com segredos. B1/B2/D090/C1/SQL/serviço/
produção permanecem abertos, Gateway indisponível. Sem commit/push/job/quota
ou outro escritor; DesktopOff na última observação.
