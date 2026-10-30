# T4 — entrypoint e retenção

2026-10-28: em revisão somente leitura; nenhum main operacional invocado,
root/estado/comando T4 materializado, Docker/PG/segredo ou thread do produto
iniciado. Binding88e220eb/32fakes e desenho aceitos antes deste entrypoint.

## O que foi medido

`tests/test_w1_bootstrap_t4_run.py`: **26passed/6,57s** no Windows3.11.3,
com CLI/owner/monitor/clock simulados. Inclui start_cycle realmente herdado,
noveOBSERVE,12checkpoints xb e replay real das suas cópias públicas de teste,
sete casos, coleta→join→restore. Reprovações/cancelamento sem sucesso falso,
HELD sem retorno/restauração/retry, deadline antes/depois sem impedir restore,
admissão canônica e pins/reuso/medidas/limite de admissão, aborto enfileirado
durante join síncrono, KeyboardInterrupt no runner com loop/tarefas retidos.
Dois testes do runner usam Loop falso; a retenção assíncrona também foi
observada em loop de teste real, apenas com recursos fictícios.

Mypy strict src/tests306 arquivos limpos para3.11/3.14; execução só3.11.3.
Helper passou lint restrito E9/F63/F7/F82 e format, sem alegar strict helper.
Ruff src/tests inicialmente encontrou imports/anotações/regex do teste;
foram corrigidos antes do fechamento. Sem alteração de fonte de produto.

## Falha do harness preservada

Primeira rodada ficou presa após6casos: heartbeat falso aguardava Event
sem obedecer flag de stop, e teardown cancelava a tarefa só uma vez quando
ela ainda transitava para HELD. Recolhido **somente** pytest próprio PID20344,
pai31940, Python base e comando exatos, criação pelo handle
2026-10-28T17:29:56.7759556Z. CIM truncava para7759550Z; tentativa de kill
que exigia igualdade desses dois timestamps recusou sem matar. Depois de
ler o valor exato, forçamos handle/identidade/comando e kill/wait desse único
objeto: exit confirmado, launcher terminou, sessão de teste53499 exit1.
Não é outra execução da prova de equivalência de identidade, não é Docker
nem morte de recurso do usuário. Nenhum pin/contrato de identidade foi alterado.

Harness corrigido para heartbeat observar stop e teardown repetir cancelamento
somente de tarefas fictícias em transição, com limite. Rodadas20/20/4,36s,
23/23/7,15s e26/26/6,57s finais. Esse histórico não é substituído por sucesso.

Seleção relacionada anterior:507pass/2deselected/50,42s, antes de incluir o
entrypoint. As duas exclusões explícitas impediram repetir a prova nativa
consumida de identidade e a unidade de PipeHandles já medida; não é suíte
integral nem gate de banco. Nenhum teste com DSN novo nesta fase.

## Pendente

Revisão do entrypoint/C1–C4 e fakes, depois raiz/estado/comando exatos antes
de execução T4 pública única. Conserva C1/B-1/B-2/D-090/SQL/produção abertos.
Gateway indisponível, candidata621 inalterada, último Desktop observado Off.

## Revisão aceita e nota de interrupção

Claude2 aceitou entry2e9fc1c9 de forma estreita, sem bloqueadores. N1 manter
HELD antes de qualquer efeito é conservador e pode reter processo sem
necessidade; aceito como limitação, sem acrescentar liberação especulativa.
N2 KeyboardInterrupt dentro de passo de pump pode terminar a tarefa sem
prova normal de EOF; segue HELD. Encerramento forçado do SO não é coberto.
N3 até duas quiesce por chamada _collect: duas no caso e, se reprovou, mais
duas na limpeza final. São até4 por owner (3s cada), não4 retries de caso.
O primeiro par entra no caso56/matriz414; o par final na pendência28. Sem
novo start/send/caso ou budget renovado do mesmo cleanup.

N4 delta entry835c2e21: KeyboardInterrupt no join também marca interrupted
antes de HELD. Teste novo comprova flag/retencão/sem restore;27/27/8,32s.
Essa marcação é informativa; antes já era impossível declarar sucesso.
Delta e preparador público c7892639/9testes em revisão antes de materializar.
