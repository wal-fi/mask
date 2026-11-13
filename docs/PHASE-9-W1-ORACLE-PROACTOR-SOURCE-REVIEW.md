# W1 Oracle: revisão da fonte Proactor

## V2: integração com SDK falso aceita sob delegação — 2026-11-13

65532 recuperada exit0/success, mesma sessão/modelo/medium, sem denials.
Root leu TODOS os deltas V1→V2 e conferiu91nós de função inalterados por
AST. Só a fonte mudou pelo programador. Formatação mecânica posterior
preservou AST. Final0a4dcd574c9c2d3f2e855d0cd3752a1a86b041966b9a628bc5ed76bcf6a798a8,
36637bytes/1077linhas; teste36b2ba54 e probe0192ef43 intactos.

S1 resolvido por snapshot isolado dos campos/métodos validados, sem
releitura da request; Exception sai fechada antes do registro e controles
conservam identidade. A request original continua retida até a fase
terminal prevista. S2 resolvido retendo transporte/handle até o término
S4, validando sua identidade antes da liberação. Pendente não vira pronto.

A MESMA sondagem medida antes do fix passou9/9 depois; RED9 anterior
3PASS/6FAIL preservado. Matriz final:1739PASS em12arquivos, incluindo
135próprios congelados,0falhas/erros/skips/deseleções,25,067s. Ruff src/tests,
lintPoC contratual E9,F63,F7,F82, format370 e mypy strict win32 nos370alvos
3.11/3.14 passaram. Runtime só Windows3.11.3/pilha QA64MiB;3.14 é estático.
142fontes protegidas conferidas intactas. State16/attempt não lidos/tocados.

Aceite SOMENTE da integração de modelo com SDK falso. Nenhum binding real
foi chamado e nenhuma prova física decorre desses verdes. N1–N16/T5/B1/B2/
D090gate2/C1/D119/TLS/ingressos/produção continuam OPEN. Gateway indisponível.
Fonte E teste congelado podem integrar juntos com evidência compacta;
nunca publicar o RED isolado como suíte verde ou os candidatos reprovados.
Ver PROACTOR-VALIDATION e evidence/oracle9-w1-proactor-tests-review-20261112/
final-validation.json. Histórico e medições anteriores seguem abaixo.

## V1: 135 próprios verdes, dois findings antes de aceitar — 2026-11-13

Execução51906 recuperada exit0/success, mesma sessão51ea0d85-05bb-4d24-
ba9a-c9627c3f832f, claude-opus-5-5/medium, sem denials. Zero escritores
confirmado depois do terminal. Root leu TODAS1007linhas/34215bytes da V1
69d283daec256c59a7bc821e010c066a6be14ed2a480c45a2d6e08763a1b8218
antes de qualquer execução do módulo. Cópia literal preservada.

Os135testes congelados36b2ba54 passaram integralmente,0falhas/erros/skips.
Mypy strict win32, fonte E teste, alvos3.11/3.14:PASS. Runtime apenas
Windows3.11.3/pilha QA64MiB;3.14 só estático. Isso ainda NÃO aceita a fonte.

Sondagem independente usa somente API pública do pump e o SDK FALSO dos
oráculos; não chama bind_proactor_pump nem toca campos privados do pump.
RED antes do fix:9casos,3PASS/6FAIL. Código
0192ef43a8126b1b09e7ce763357b5244e2b214fafe0bbed6bed1bbdbf8004cc;
probe-source-boundaries-red9.json preservado. A execução inicial como
arquivo direto não achou o pacote tests; não é finding de produto. A
medição válida foi por python -c/runpy a partir da raiz do checkout.

## S1 — aquisição de campos S0 pode expor a exceção original

_request_ok lê atributos da request e dos events sem converter Exception.
schedule_start também relê record_id, events e stdin_pipe fora de try
antes da entrada. Uma propriedade que levanta OSError com canário sintético
atravessa a API como OSError contendo a mensagem original; não é PumpFault
fechado. Reproduzido no primeiro acesso a record_id/método de events e no
segundo acesso a record_id/events/stdin_pipe:5falhas. Não é vazamento de
credencial real nem prova nativa; é quebra do contrato fechado desta API.

Corrigir todas as aquisições S0 pertinentes antes de admissão/registro.
Exception deve sair como PumpFault(args==(), sem cause/context), mantendo
zero efeito, ausência de entrada e reuso válido do mesmo id. Controles
preservam a mesma identidade, sem bool/latch/registro. Os2controles do
roteiro já passam e devem continuar passando.

Não forçar leituras redundantes: um snapshot validado que lê cada campo
uma vez é legítimo. O roteiro aceita admissão válida quando o segundo
getter nunca foi chamado; só exige falha fechada quando a exceção foi
realmente injetada. Preservar a retenção da request original nas fases
definidas em P3 e a validação dos campos; não mudar interfaces ou oráculos.

## S2 — liberação anterior ao retorno S4 produz fault falso

Com ProcScript(prestart=True), todos os fatos podem estar pendentes antes
da conexão dos pipes, como o SDK textual documenta. Um closed() que chama
handle.close() é permitido pelo contrato do handle dentro dos callbacks.
_on_connection_lost marca lost e closed_delivered; _maybe_release limpa
entry.transport antes de a coroutine S4 validar o retorno do transporte.
Quando S4 termina, t is entry.transport falha porque entry.transport já é
None. A condução levanta PumpFault apesar de fatos/close válidos.

Reproduzido:1authorize, sequência started/pipe_lost/pipe_lost/exited/closed,
1close explícito,0sdk.kill e PumpFault indevido. O controle positivo que
fecha depois da condução passa, assim como todos135oráculos originais.
Corrigir a ordem/posse: reter os insumos necessários até validar o retorno
S4; depois liberar quando as condições reais forem atendidas. Manter a
checagem de identidade de transporte (inclusive foreign_transport),
retenção de S4 pendente e quiescência honesta. Não ignorar o fault por
encontrar None nem declarar cleanup físico pelo close lógico.

## Estáticos, formatação e limites do lote

pyproject.toml já exclui docs/poc do lint de produto. O gate restrito PoC
existente é E9,F63,F7,F82 (PORT-OWNERSHIP-VALIDATION); passou na V1.
A invocação exploratória do lint amplo foi preservada:33diagnósticos,
incluindo nomes/API PumpFault e imports locais EXIGIDOS pelo desenho.
Não renomear API, mover imports nativos ao topo, adicionar supressões ou
reescrever tipagem que já passa para acomodar esse lint fora do escopo.
Gate de produto src/tests permanece obrigatório na integração final.
Format-check da fonte ainda FAIL; root pode aplicar Ruff format mecânico
com prova de AST igual após os fixes. Não mexer no teste congelado.

Próximo incremento: mesmo único Claude2/sessão/Opus5.5/medium, Read/Edit/
Write SOMENTE docs/poc/oracle9_w1_proactor_pump.py, sem comandos/execução,
commit ou push. Ler esta revisão, P3 e TODO PROACTOR-REVIEW/R8, teste135,
sondagem/red9 e contratos fixos. Root lê TODOS os deltas antes de repetir
a MESMA sondagem e os135, ampliar QA ou publicar. Fonte privada NÃO aceita.

Ownera5/testese85/f86/15upstream/app124/state16/attempt fixos. Sem AGY,
efeito nativo/loop/socket/thread/processo/guard/sinal/Docker/PG/SQL,
runtime/config/privado/ambiente/binário ou valores operacionais/deploy.
N1–N16 e todos gates de produto continuam OPEN; Gateway indisponível.
