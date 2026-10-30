# T4 — monitor e limpeza por posse, somente fakes

2026-10-28, sob delegação. Camada nova em docs/poc/w1_bootstrap_watchdog.py,
3e98cd31308545fab264c67173c5b5ecc33c11daca5aabc1ba1757b0921f51a5.
Executor2fdc0084/calibração22casos aceitos pelo Claude2; identidadedc248/
prova nativa única aceita. Nenhum coordenador/main/root/estado/comando T4.

## Contratos

Snapshot congelado contém só task/case/argv públicos capturados, CID e
PID/FILETIME opcionais exatos, nunca owner/Process/transporte/tarefas/seed.
Store com lock tem main como único publisher. Heartbeat15s e pós-B600s;
armB uma vez, antes de B só heartbeat. Erro de monitor também dispara abort
e HELD; relógio retrocedido não autoriza ações externas. Callback fechado
request_abort é o único sinal ao main, ack≤2s.

Namespaces capturados/pinados próprios para preparação/execução; executor
já cria seu próprio bounded/identity/loop. Intenção reidratada dos campos
**já admitidos do snapshot do main**, sem chamar construtor que relê fonte.
É código confiável, não sandbox de introspecção nem entrada de usuário.
Posse usa compare do helper aceito contra nome/task/imagem/argv/labels próprios
por subconjunto; drift de perfil ou label extra não impede cleanup próprio.

Emergência nunca libera: mantém held=true/released=false inclusive após CID
ausente, até o main recolher e observar ausência **nova** após seu ticket.
PID desconhecido não é adivinhado; só CID identificado pode ser recolhido,
com confirmação posterior obrigatória do main. CLI conhecido primeiro pelo
PS revisado; erro encerra sequência, inclusive mismatch, sem matar outro PID.
Depois Lock compartilhado1s, ausência por CID, inspect/posse, kill só se vivo,
reinspect/parado/PID0, rm semforce e ausência. Sem retry nem força. Indeterminado
sem CID mantém pendência, nunca usa nome/globalvazio como prova de conclusão.

Thread não-daemon registrado antes de start; falha de start marca abort/HELD.
close sinaliza Event e join50s; só retorna prova de thread encerrado, não
prova de owner/CID ou sucesso do lote. Falha/exceção/join ainda vivo mantém
HELD. Em produção do ensaio, disparo implica sempre NOT_PASSED e ausência
do watchdog nunca pode ser Absent do main. Coordenador ainda deve aplicar
essa regra e confirmar cleanup global/boot/PID antes de restaurar Desktop.

Logs emergency-NN.json em xb, categoria/ação/CID/PID públicos, intent antes
e COMMAND_OK após comando; sem raw stdout ou canário/digest. Falha de log
interrompe e mantém pendência. Sem objeto asyncio do main no thread;
ele usa só seu próprio loop do executor para chamadas públicas.

## Medições Windows3.11.3 com fakes

**26pass/1,14s**, testes
a216ca5a5b208b2f060477bdc06bafd40985a26815288aa000a20ae672add378.
Thread, eventos de espera e executor **simulados**, clocks injetados;
nenhuma thread real iniciada ou espera real15/50s. Cleanup usa cópia de
inspect histórico; nenhuma nova observação Docker/CIM. Campos imutáveis,
fonte indisponível, label extra, ausência anterior, falta de posse, lock
ocupado, identidade do CLI recusada, heartbeat16/global600, erro de monitor,
start/join/alive e tipos de identidade cobertos. Mismatch aqui simula falha
fechada do executor; PID reaproveitado real não foi fabricado. Igualdade de
FILETIME e recusa do timestamp errado foram medidos só na prova P1 própria.

Ruff/mypy3.11 do teste e lint restrito do helper; sem claim de tipagem estrita
para o helper. Erros iniciais de anotação do teste corrigidos antes de revisão.

## Próximo e limites

Código/fakes em revisão somente leitura. Ainda falta integração completa:
main possui foreground e callback de cancelamento, captura PID/FILETIME
logo após start retornar/lançar, heartbeat real, Lock comum e coleta depois
de emergência antes de nova ausência/ticket. P3 dos caminhos antigos
inacessíveis será provado no coordenador, não nesta camada isolada.
Join/spawn travado não foi provocado no SO; ramo de joinfalho foi simulado.

Nada da T4 foi executado. Nenhum DockerCLI/novoPG/rede/secret/worker/SQL,
mudança de produto/dependência ou serviço. Prazos calçados no plano atual:
45emergência/50join/571pós-B, sujeitos a syscall que não retorna. Estado,
raiz, comando e ciclo ainda precisam de revisão antes de A. B-1/B-2/D-090/C1/
produção abertos, Gateway indisponível. Sem commit/push/job/segundo escritor.

Claude2 aceitou3e98cd31 como componente,26fakes, sem bloqueador. Limitação
L1 preservada: mismatch/erro do killCLI interrompe o executor pegajoso e a
remoção do CID não é tentada pelo watchdog; fica HELD para o main/recovery.
Não trocar executor nem renovar orçamento para contornar esse erro.
Ack só confirma sinal recebido, não cancela a emergência; Lock arbitra a
concorrência. Integração deve consultar metadata somente após **join positivo**;
se join falhar, registrar status fixo THREAD_JOIN_UNPROVEN sem ler campos
mutáveis do thread. Evento fired pode ser consultado de forma thread-safe.
