# W1 Oracle: revisão da fonte do bind Proactor

2026-11-13. Claude2, mesma sessão 51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5 / medium, foi o único programador. Execução 56218 terminou
exit 0 / success, sem denials; terminal recuperado. Zero escritores novos
ou próprios confirmado depois; a clarificação do usuário sobre os CLIs
legados foi respeitada, sem ler outras conversas ou configurações.

## Escopo conferido

Root leu TODO o diff da fonte. A comparação de AST confirma que todos os
outros nós do módulo ficaram iguais, inclusive as classes, enums e métodos
do pump. No wrapper, imports locais e guardas anteriores à construção são
idênticos; a cauda foi substituída por uma única delegação. O único helper
acrescentado é `_bind_over`, com a assinatura do desenho B2 / revisão B4.

A referência de classe serve como fábrica sem argumentos e tipo exato.
Uma falha ordinária da fábrica vira PumpFault novo fora do except; um
controle atravessa pela identidade. Sem retorno, não se afirma loop
conhecido ou ausência de efeitos parciais. Em recusa de objeto conhecido,
o helper tenta close uma vez fora do except primário e dentro de seu
próprio try. O primeiro controle vence os posteriores; controles não têm
sua veracidade consultada. Falhas ordinárias não expõem args ou cadeia.
O local `loop` continua no frame do helper ao levantar o Throwable.

Root conferiu os oráculos de contexto preexistente, identidade, uma
chamada explícita de close e retenção pelo código do próprio helper. O
witness recusa a referência contaminante do teste; a sonda independente
continua detectando a remoção deliberada desse filtro.

## Medições e formatação

A fonte entregue 16030626 passou os 1.784 testes relacionados e os checks
de Ruff e mypy. Format-check pediu apenas unir a assinatura do helper.
Root aplicou Ruff mecanicamente, comprovou AST idêntica e releu o delta;
a fonte final 3cb74292 tem 38.627 bytes / 1.109 linhas. Format-check dos
371 arquivos e os 45 testes do bind passaram novamente sobre essa fonte.
Os 45 oráculos f6724a8f permaneceram byte a byte iguais ao RED congelado
antes da implementação. Nenhum assert, probe, pin ou contrato foi afrouxado.

## Aceite e limites

Aceite sob delegação apenas da integração pura revisada. Fonte e teste
congelado integram o mesmo checkpoint; o RED sozinho não é suíte verde.
Nenhum finding novo neste incremento. Ver BIND-VALIDATION e evidência
compacta bind-final-validation.json; medições anteriores ficam preservadas.

O wrapper real nunca foi chamado. Reter Throwable/traceback é obrigação
prospectiva do chamador ainda ausente, não liberação física. Construção
parcial sem retorno, close bloqueado, controles assíncronos na entrega,
guardas reais e contenção continuam sem prova nativa. N1–N16 / T5 físico /
B1 fim a fim / B2 / D-090 gate 2 / C1 / D-119 / TLS / ingressos / produção
seguem OPEN. CliPlan, receitas e readmissão continuam NOT_PREPARED.
State16 e a tentativa consumida não foram lidos ou tocados.
