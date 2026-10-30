# T4 v2 — execução única real, 2026-10-29

Estado: **ORACLE9_T4_V2_VERIFIED**, exit0, fatos aceitos pelo Claude2 (39884).
Escopo: canários públicos no Docker local Oracle9.8/WSL2, cliente nativo
Windows3.11.3. Não é worker SQL, B-1 fim a fim, B-2, C1 ou produção.

## Procedimento e identidade

Desenho27358, código14731/76265 e proposta52272 revisados antes dos efeitos.
Fontes consumidas, não editar/reexecutar: perfil3a5bb9a3, main28b56013,
exportaeade45d, prep8e024cf4; dependências originais preservadas. Novo root:
`C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-t4-v2-20261029-de8e832ca4c67fd35f3647779adfaad0`.
Task `42d363a1115633d15fbb809fc0dc666e`. Estado3305bytes/bec0accd e script
b01ce0b2 conforme proposta, materialização única conferida com bytes iguais,
onlyattempt/argv literal-I-B iguais. DesktopOff13:11:00.1125191Z antes da
invocação única do script; sessão10282 terminou0. Não houve retry, outra CLI,
outro writer, banco ou segredo. Proposta e materialized-proof preservados em
`docs/poc/evidence/oracle9-t4-v2-prep-20261029/`.

Imagem exata621cc7f7, sem rebuild/pull/instalação nova. Mesmo canário, frame,
leitor e tetos, somente a expectativa StdinOnceTrue mudou conforme diagnóstico.
Os registros da rodada T4 antiga0566 não são reescritos nem sua causa atribuída.

## Resultados reais

12 checkpoints/replay, A→B119281ms, journal final
`89238823ba259a16d637eb36139056c9c88d6d125d17500725d9b62db6f333cc`.
66 comandos registrados, todos exit0. Sete casos e sete owners liberados;
sete registros próprios removidos, ausências posteriores e inventário vazio.
Watchdog joinedtrue/firedfalse/heldfalse. Campos releasedfalse/cid_absentfalse
do watchdog são do caminho de emergência não disparado, não dos owners:
os sete owners têm releasedtrue e assert_released passou.

| Caso | Entrega no pipe local | Resultado |
| --- | --- | --- |
| normal | SENT | 16384bytes iguais no container, UID10001/PID1 |
| retain | SENT | CLI recolhida e CID ainda Runningtrue/UID70, depois removido |
| bad-ready | NOT_SENT | recusa de READY, sem envio posterior |
| blackhole | SENT | envio local aceito nesta rodada, sem alegar leitura pelo container |
| flood | SENT | excesso de saída recusado e recursos recolhidos |
| cancel-start | NOT_SENT | cancelamento sem envio tardio, recursos recolhidos |
| reader-negative | SENT | quatro negativos retornaram FRAME |

`normal` e `reader-negative` observaram EOFtrue (1ms e0ms respectivamente).
EOF continua informativo; o frame se delimita sem depender dele. SENT sozinho
prova apenas handoff local; igualdade16384 é o oráculo adicional dos relatórios.
Retain vivo é raw distinto e tem ligação com inspect-cleanup-retain registrado.
Inspect direto inicial de cleanup continua não capturado, flagfalse explícita.

Desktop restaurado OFF_CONFIRMED, stop13,297s e processos app/backend ausentes
em13:15:07.9767894Z. Nenhuma nova imagem/container/worker ou serviço deixado
em execução. A imagem candidata continua local, não significa serviço instalado.

## Exportação e preservação

Depois do exit0 e das provas de recursos, uma chamada do exportadoraeade45d.
Destino `docs/poc/evidence/oracle9-t4-v2-run-20261029-42d363a11156/`.
53 fontes/732390bytes,53publicadas/0retidas, todas com S1 recalculado allowed.
TransportSHA:
`3a274347849ea10c37e3ef05395716c94d7c3c084d5fefedcf751f81ffeb09bc`.
Nenhum raw foi lido em ferramenta/conversa antes desse filtro. Brutos, aliases,
relatórios, estados e fontes originais permanecem intactos. Eventual suplemento
do console é observação separada, não parte das53fontes do transporte.

Preparação medida antes da rodada:93testes novos (65+28), seleção relacionada
478passed/2deselected100,52s, dois nativos consumidos explicitamente excluídos.
Ruff/format320 e mypy strict311/314 em316arquivos limpos, execução só3113.
Nenhuma suíte de PostgreSQL, frontend ou pacotes foi rodada neste lote público.

Limites: somente perfil/cliente/canário/image/kernel medidos. Sem certificação
de kernel EnterpriseLinux/SELinux, SQL, segredos, contenção total ou serviço
foreground. B-1/B-2/D-090gate2/C1 permanecem abertos, Gateway indisponível.
Sem commit/push, quota/job ou segundo escritor.
