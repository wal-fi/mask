# W1 — primeira rodada pública abortada, recursos próprios restaurados

2026-10-27, execução única após aceite pelo Claude2 do4bc0b083, estado
d43f3b2a e comando6419465b. Exit1/NOT_PASSED. Não repetir main/A/B nem
editar o attempt consumido para obter sucesso.

## Fatos medidos

Desktop inicialmenteOff, start próprio PID27644/FILETIME134375830785499297.
Nove observações e entrada B aceitas pelo portão em código; último estado
B_CONSUMED, boot134372287595000000, tickA354354562/tickB354477265:
122703ms. Foram persistidos anchor/last/count/phase, não todos os samples
intermediários; **não há replay independente dos nove gaps/READY**. O fonte
hashado aplicou os gates durante a execução; essa limitação não é apagada.
Próxima versão deve guardar cada checkpoint imutável, sem inventar passados.

Preflight CLI exit0: kernel6.18.54.1-microsoft-standard-WSL2, contexto local,
inventário vazio, base87871290 com os3layers/Config6chaves/4labels esperados.
Imagem-base observada agora, não apenas fixture.

Create-install exit0 criou CID
72891af0601c6b787a18673db037a4155e0cec344d50605ecc540eab8160c883.
Inspect exit0, mas CONTAINER_LABELS_EXACT recusou antes de cp/start/pip.
Cleanup repetiu o mesmo validador de aceitação e também recusou. Nenhuma
instalação, sonda, commit Docker, SQL, banco ou worker foi executado.
Resultado honesto: owned_cleanupfalse/inventory_restoredfalse,
desktop_statePENDING. Não declarar que o host foi restaurado.

## Diagnóstico somente leitura, depois do término

Uma inspeção adicional pelo CID exato, exit0. Identidade task/source/manifest/
nome/imagem conferida antes de guardar a resposta. SHA04fe93b2 é **igual**
aos dois inspects da rodada. Statecreated/Runningfalse/Pid0/StartedAtzero.
Todos os checks do validador original de segurança/perfil passam; somente
o requisito adicional de herdar desktop.docker.io/ports.scheme diverge:
a imagem possui4labels, o container criado possui apenas os3labels próprios.
Nenhuma causa foi atribuída ao Docker/Desktop/API para essa diferença.
Não se afrouxou nenhuma proteção nem se repetiu instalação.

Transporte de11arquivos/15652bytes para
`docs/poc/evidence/oracle9-w1-run-attempt1-20261027/`, manifesto SHA
ce09d005178d52fb090886e2de70fa42463b6d0bd7db6b396d1dea82f71976bf.
Diagnóstico e inspect exato estão nos artefatos attempt1-diagnostic/inspect.
Originais e fontes4bc0b083/7540b7bf/566c46a8 preservados.

## Recuperação proposta, sem nova instalação

`docs/poc/oracle9_w1_restore.py`9d4fa8b9587221bb67ed7f402010317fce4173b2c78e52c15b38ccc1a7d07bfd.
Usa4bc0b083 como biblioteca admitida, nunca seu main/start_cycle/perform_b.
O transport manifest fixo admite os witnesses do attempt falho. Antes de rm:

1. Uma inspeção por CID, rawSHA04fe93b2 exato, identidade e validador original
   completo (caps/namespace/network/memory/argv/etc); conjunto exato3labels
   próprios e Statecreated/Runningfalse/Pid0. Divergência aborta sem rm/kill.
2. rm somente esse CID, **sem force e sem kill**, exit0 e ausência por CID.
3. Inventário global vazio fresco; restauração pelo método já revisado:
   boot exato, PID/FILETIME próprios, novo inventário vazio, stop limitado
   e até10 consultas de processos. Nenhum kill por nome/imagem/prune.
4. Não editar resultado ou ownership antigos. Novo root/sentinel/result
   separado. Qualquer falha permanece pendente, sem retry.

14 testes focados com fakes aprovados,2,80s. Dois vermelhos iniciais eram o
fake omitindo timeout3 do inventário; corrigido o fake, sem alterar recuperação.
Ruff check/mypy3.11/3.14 em298src/tests e format em300 (inclui2helpers) limpos;
helpers têm lint E9/F63/F7/F82, não alegar tipagem deles. Runtime sóWin3.11.3.
Teste089fa17e. Nenhuma recuperação real executada ainda.

Root preparado:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-restore-20261027-e7b054beeff149d68b39aff29e0771cc`,
somente state.json invokedfalse/SHA
72f89bfd22195562c34ccba65b1bb6a52ddfd9f71ab45710cb929cf7d8564047.
Estado/comando exatos em oracle9-w1-restore-preparation/command-20261027.
Comando verifica Pythonbfff5171, runner4bc0b083, restore9d4fa8b9, stateSHA e
root fresco; uma invocação -I-B, exit propagado. Código/estado/procedimento
de recuperação seguem para revisão antes de rm/stop. Sem uso da imagem,
novo A, commit/push/deploy ou job. B-1/B-2/D-090/C1/SQL/produção abertos.

## Recuperação executada uma vez, após aceite do Claude2

Código9d4fa8b9, estado72f89bfd e comando exato revisados antes da invocação.
Resultado exit0/W1_OWNED_RESOURCES_RESTORED. Inspect manteve SHA04fe93b2,
perfil original completo, created/Pid0 e3labels próprios. rm sem force/kill
exit0; ausência CID e inventário global vazio exit0. Boot/PID/FILETIME próprios
revalidados pelo método revisado; stop14,531s/exit0 e primeira consulta de
processos devolveu[]/exit0. Resultado owned_cleanuptrue/inventory_restoredtrue/
desktop_restoredtrue/OFF_CONFIRMED. Oito comandos registrados, todos exit0
(seis DockerCLI e duas consultas PowerShell; sampler usa seu próprio helper).

Nenhum kill, imagem nova, install, SQL ou banco. O original da tentativa
falha continua com exatamente os11arquivos/bytes transportados; o seu resultado
NOT_PASSED não foi reescrito. A recuperação tem root e artefatos separados em
`docs/poc/evidence/oracle9-w1-restore-attempt1-20261027/` com manifesto próprio.
Resultado segue para revisão somente leitura. Próximo desenho deve distinguir
ownership de aceitação, explicitar labels de CID/imagem e persistir checkpoints
imutáveis. Não há nova tentativa autorizada pelo aceite dessa recuperação;
trabalho seguinte segue sob delegação e requer revisão antes dos efeitos.

Claude2 aceitou a evidência da recuperação c1351f16 como baseline, sem
ressalva sobre os fatos registrados. Não recalculou os SHAs em shell; a
conferência de bytes foi feita pelo host. O desenho seguinte foi aceito
como direção com R1–R5, incorporados antes do código no REVISION-PLAN.
