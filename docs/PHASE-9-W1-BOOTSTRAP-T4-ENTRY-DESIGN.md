# T4 — entrypoint futuro, retenção e admissão

Proposta de integração sob delegação,2026-10-28. Binding em revisão. Nenhum
entrypoint/raiz/estado/comando criado ou executado com base neste documento.
T4 pública, sem PG, segredo, SQL, instalação, commit ou alteração da imagem.

## Admissão e tentativa única

Arquivo separado `docs/poc/w1_bootstrap_t4_run.py`, carregando apenas as
definições do binding por hash. Root nativa exata sob Temp deste usuário,
nome `maskgw-oracle9-t4-20261028-<32hex>`, diretório regular não-reparse e
somente attempt.json antes de iniciar. Estado canônico com kind fechado,
task32, phaseFRESH/invokedfalse, program4bc/v2b593/host/entry hashes,
pins exatos das seis bibliotecas herdadas e cinco componentes T4, imagem
fixa621 e as sete medições de comando. Pins de runtime/CLI/Desktop/PS/
contexto/stdlib do canal iguais aos já aceitos. Sem aceitar estado reaberto.

Antes de A: runtime Windows3.11.3, flags-I-B/sem optimize, diretório/estado,
fontes, entradas e medições. Trabalho síncrono de admissão/pins/construção
≤3s depois do retorno; ultrapassar aborta antes de Desktop/create. Não é
interrupção de leitura do SO. Gravar invoked.json xb e estado INVOKED antes
de iniciar monitor/A. A preparação futura cria somente root/estado públicos,
nunca invoca main, Docker ou relógio do Desktop. Root e comando exatos vão
para revisão depois dos testes, antes da execução única.

## Ordem do fluxo

Monitor/heartbeat antes de A. start_cycle herdado conserva janela, boot,
nove observações, preflight antes de O9, READY e B consumido duravelmente.
Verificar journal completo/replay antes do primeiro canário. perform_b novo
é a única ação B. Não chamar mains antigos, run_own, instalação ou commit.

Em erro ou cancelamento: registrar somente categoria fechada, não mensagem
original/traceback; abortar ciclo se houver. Foreground deve estar terminado
antes da limpeza; se cancelamento não concluiu, HELD, não iniciar limpeza
concorrente. cleanup_owned faz quiesce/ticket/ausência/close dos recursos
conhecidos. Não repetir create/caso, não criar novo executor para contornar
falha persistente. Create indeterminado permanece pendente.

Precisão nova: **join do monitor antes de restore_desktop**, depois da
limpeza e de verificar tarefas/owners conhecidos. Isso evita que o thread
entre tarde no cleanup quando o main já restaurou o Desktop. Se join falha,
não ler metadata mutável nem restaurar Desktop. O heartbeat é recolhido no
mesmo passo. O join de50s substitui a ordem proposta inicial de stop depois
da restauração; não muda caps do canal/worker. O limite de600s pós-B continua
conferido pelo main antes/depois de restore; durante restore aplicam-se os
limites herdados, sem promessa de interrupção de spawn/syscall que não retorna.
Não alegar watchdog independente ativo depois do join.

Só então restore_desktop herdado, com boot/identidade e inventário global
vazio antes de stop. Não stop/prune de recurso alheio; inicialmente ativo
fica ativo. Janela nominal571s continua abaixo600s, sem aumento em voo.

## Liberação versus retenção

Loop só pode encerrar depois de todos os owners/tarefas/CLI/pipes recolhidos,
ausências novas e monitor joined. Reprovação de um oráculo pode terminar com
exit1 se a limpeza ficou comprovada; sucesso exige ainda sete casos,
journal/inputs íntegros, Desktop/inventário restaurados e watchdog não
disparado. Sem inventar sucesso por arquivo parcial ou stdoutprefix.

Se assert_released falha, persistir resultado NOT_PASSED e fase HELD,
reter Host e loop com tarefa-raiz viva. Não fazer asyncio.run retornar nem
fechar/cancelar automaticamente as tarefas de spawn/transporte. Não rodar
retry de caso/limpeza indefinido ou renovar deadlines. Intervenção futura
será recuperação específica contra o journal e identidades. O processo
imprime categoria/estado/caminho públicos para permitir acompanhamento.

Runner externo usa loop explícito e não o encerramento cancelador de
asyncio.run. Exceções/sinais inesperados enquanto há recursos mantêm o loop
e owner em retenção; não entram em finally que fecha o loop. Encerramento
forçado do próprio SO continua fora da garantia; isso não é auto-restart,
daemon de produto nem controle de produção. Testes simulam retenção por
checkpoint observável, sem criar processo preso no host.

## Testes antes de efeito

Admissão com estado/raiz/flags/pins adulterados e reuso recusado. Fluxo inteiro
com A→noveOBSERVE→READY→B→journal→sete casos→cleanup→join→restore e métodos
herdados identificados. Falhas em start/READY/caso/journal/cleanup/join/save,
cancelamento e retorno tardio; HELD não retorna nem fecha loop, não restaura
Desktop, não inicia outro canário. Reprovação recolhida retorna1 e sucesso
realmente completo0. Apenas fakes e arquivos públicos nesta fase.

## C1–C4 da revisão, antes de efeito

Binding88e220eb/32fakes aceito. Ordem join antes de restore aceita com
pré-condições verificadas, não presumidas: owners assert_released, tarefas
do host concluídas exceto heartbeat, foreground concluído e lock livre.
O callback tardio apenas fica enfileirado durante join; emergência termina
no próprio loop e não toca tarefas do main. Teste desse enfileiramento é
simulado, não execução nativa de emergência concorrente.

C1 escolhido: na retenção por falha de coleção, **não parar nem substituir
o monitor**, deixando seu disparo único acontecer; conservar Host/loop e
thread para recuperação específica, sem novo cleanup automático. Não emitir
release nem exigir join bloqueante enquanto suas pré-condições falham.
Depois de um join que já foi tentado e falhou, stop já foi solicitado pelo
componente; registrar HELD e supervisão independente não comprovada, sem
restart de monitor. Isso não é vigia contínuo após a emergência única.

C3: tempo pós-B≥507s antes de restore marca RESTORE_MARGIN; ainda assim
restaurar com prova de posse/boot/inventário. Depois,≥600s ou relógio
regredido marca reprovação. Nenhum estouro autoriza deixar o host alterado
quando a restauração segura é possível. C4: interrupção externa é capturada
no runner explícito, sem fechar loop ou cancelar tarefas próprias; retém
contexto e reentra no mesmo loop, registrando fase/categoria/root. Encerramento
forçado do SO permanece fora da garantia.

Implementação inicial entry2e9fc1c9, sem raiz/estado/comando operacional;
26testes simulados6,57s. Código vai à revisão antes de preparar artefatos.

## Notas do aceite do entrypoint

2e9fc1c9 aceito sem bloqueador. Delta835c2e21 só marca interrupted quando
KeyboardInterrupt chega no join;27testes8,32s, sem outra mudança de fluxo.
Até duas quiesce por _collect; no máximo quatro no owner se o caso falha
e há limpeza final:6s dentro do caso56 e6s na pendência28. Não repetir
caso/start/send, e não reabrir o deadline22s de uma mesma coleta.
Interrupção dentro de passo de pump pode perder prova de EOF e reter HELD;
força do SO fora da garantia. Liberação antes de qualquer efeito permanece
conservadora, podendo reter sem recurso quando a supervisão nem chegou a A.
