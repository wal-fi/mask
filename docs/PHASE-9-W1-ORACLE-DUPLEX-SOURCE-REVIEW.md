# W1 Oracle: revisão da fonte duplex

2026-11-11. Continuidade sob delegação, não aprovação individual. A rodada
anterior foi progresso: testes e RED195 preservados no commit local43f2a48.
Claude2 programa na sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, modelo
claude-opus-5-5/medium; root revisa e executa QA. Não há efeito nativo.

## V1 lida integralmente; ainda não aceita

CLI20996 encerrou0/success em490626ms, sem recusas de ferramentas. Zero
escritores confirmado antes da revisão. Só a nova fonte foi criada:
41f3de09ca5f3988e510d0ff288882cf610f2bdfd496276ce6f63a866e7f963d,
32885bytes/931linhas. Root leu todas as linhas antes de executar a fonte.
Teste97c26fbf/1935linhas permanece intacto, assim como13protegidos/app124.

Os195testes passaram em7,640s, sem falhas/erros/skips. Esse verde não
prova sozinho o contrato. Ruff restrito E9/F63/F7/F82 passou; format tem
1hunk pendente. Mypy strict3.11/3.14 apontou20erros em cada alvo (binding
inferido como Any|None, retorno Any de run, shape do process e atribuição
do retorno None de _await_line). Diagnósticos preservados como dados.

## Quatro regressões independentes medidas ANTES da correção

Sondas de root são QA, não produto nem alteração do teste congelado.
Script imutável em evidence/oracle9-w1-duplex-source-review-20261111/
independent-probes-v1.py.txt; execução sobre portas falsas/HostReactor real,
1,328s,0PASS/4FAIL. Nenhum SO/rede/PG/SQL do produto foi acionado.

1. **P2: status não lê somente cache.** Duas chamadas públicas a status()
   invocam HostReactor.status duas vezes. R8/desenho exigem leitura de
   observações já em cache. Guardar o status fresco validado no construtor
   e atualizar snapshot durante a execução/feed, inclusive recusa normal
   do reator. status público não pode invocar callback, nem do reator.
   Controle BaseException não pode disparar atualização/callback no handler.
2. **P2: perda da exceção original na colheita.** outcome() levantando uma
   instância RuntimeError conhecida mantém op, mas SlotView.outcome é None.
   _Cell.error bool não retém a observação original. R7.1/R8.2 exigem
   primeiro valor OU erro original em cache antes de validar/recusar.
   Guardar a instância original de erro de done/outcome no cache do slot,
   sem reobservação nem divulgação em repr/mensagem/cause/context.
3. **P2: lookup repetido escapa sem sanitização no construtor.** Clock.now
   é callable no primeiro lookup, mas levanta RuntimeError no segundo;
   a fonte propaga RuntimeError cru em vez de PORT fechado. Obter/validar/
   reter o mesmo callable uma vez é solução válida, ou recusar fechado
   fora do handler. Nunca devolver erro original/causa/contexto. Aplicar
   o mesmo invariante aos demais métodos obtidos após teste de forma.
4. **P2: prazo de dreno começa tarde.** EOF já está em cache enquanto INIT
   ainda espera resultado NOT_SENT. A fonte só ancora depois do recibo,
   estendendo o prazo de110.046875 para111.03125 (0.984375s). Desenho5.3.2
   exige primeira transição/observação: EOF/exit em cache, DRAINING/ENDING
   ou recibo kill, mesmo com efeito nativo ainda ativo/FIFO não vazia.
   Capturar uma vez no momento observado apropriado, sem renovar depois.
   Ainda entregar recibo antes de Line/Exited; a âncora não autoriza feed
   concorrente, descarte de resultado, timestamp retroativo ou kill.

## Correção autorizada somente na fonte

Mesmo Claude2, Read/Edit/Write só docs/poc/oracle9_w1_duplex_bridge.py.
Ler toda esta revisão e as4sondas; corrigir os4findings e os20diagnósticos
de mypy/formatação. Sem ignore/cast/supressão, relaxar tipos/asserts ou
modificar testes. Anotações de namespace dinâmico devem acompanhar a
validação real já exigida; não esconder validação inexistente em Any.
Oráculos congelados195 e sondas de root ficam intactos. Nenhum comando
ou execução pelo programador. Root lerá todo delta antes de novos gates.

V3+R8/R9 são o contrato. A fonte não deve criar outro motor de protocolo,
genérico de SO ou API de cleanup. Done continua candidato, nunca release.
Sem Docker/PG/SQL/nativo/runtime/config/privado/binário/root/nonce/deploy.
Estado16/attempt intactos. Gates nativos/produto continuam abertos;
Gateway indisponível. Nenhum push do incremento parcial foi realizado.

## V2: quatro findings verdes; tipagem e adoção tardia ainda pendentes

CLI2071 encerrou0/success em197328ms. Root leu todo o delta da fonte
b3ea5e2881b134f9e70dd0dcbea140bb7d2474d9048c2e42cf4b501bcccfde33,
35343bytes/969linhas.195testes PASS e as4sondas imutáveis PASS. A âncora
medida agora é110.046875, sem extensão. Erro original retido, status sem
callback e lookup único do callable confirmados. Asserções antigas intactas.

Restam15diagnósticos mypy em cada alvo3.11/3.14, todos no mapa local names
de _bound_reactor_or_none, inferido Any|None. Anotar esse namespace conforme
o retorno real dict[str,Any], preservando todos os testes de tipo existentes,
é uma correção de tipagem válida; não remover validações. O único hunk de
format é a expressão zero25 em _may_start. Diagnósticos e hunk exatos em
evidence/oracle9-w1-duplex-source-review-20261111/v2-statics.json.

Sonda adicional late-spawn-probe.py.txt medida RED antes do fix: spawn
é colhido após overall e guarda processo no outcome original, mas o campo
status.process permanece None. Não há perda do recurso: op/outcome estão
retidos. Há uma lacuna de adoção/coerência com R7.1§3.2.4: quando há
SpawnOutcome exato com process não nulo em cache, adotar essa referência
antes das recusas, inclusive overall. Fazer a adoção no ponto de cache,
sem método/callback/efeito adicional ou validar depois do prazo. Manter
op/outcome originais, recusa OVERALL_DEADLINE e zero novos read/wait.

Próxima correção SOMENTE fonte: tipagem, hunk de formato e adoção tardia.
Teste congelado195 e todas as sondas ficam intactos. Root relê o delta e
repete gates apropriados. Nenhum gate nativo/produto fechado neste verde.

## V3: tipagem fechada; checagem inicial ainda falha antes do fix

CLI67370 encerrou0/success em22736ms. Delta integral lido: anotação do
namespace, hunk de formato e adoção do processo no ponto do cache. Fonte
2b58c6d18b9d4475383195396709367b9e8dba27358e2d0f200dc4ca7fac1c9f,
35615bytes/971linhas. Ruff restrito/format e mypy strict3.11/3.14 passaram.
As4sondas e a nova sonda de spawn tardio passaram, sem alterar os oráculos.

Sexta sonda initial-deadline-probe.py.txt foi medida RED antes da correção:
clock inicial finito1e308 (domínio permitido), somado a overall120 arredonda
para o mesmo instante. A fonte inicia1spawn e só depois recusa SPAWN; o
prazo global já estava vencido. Não se afirma que esse seja um relógio
operacional real; é um limite numérico do contrato finito e isola a falta
da observação/checagem antes do PRIMEIRO begin. Nenhum processo real criou.

Correção mínima: observar now novo e aplicar overall imediatamente antes
do begin_spawn_into inicial, como já se exige dos outros begin_*. Se o
prazo de spawn também já passou, recusar SPAWN antes de chamar a porta,
depois da precedência de overall. Testes e6sondas congelados; só fonte.

## V4 revista e gates finais verdes

CLI71321 encerrou0/success em15858ms. Root leu o delta de3linhas: fresh
antes do primeiro begin, prioridade do prazo global e recusa do spawn já
vencido antes de chamar a porta. Sem rebase ou estreitar domínio numérico.
Fonte final5a09be1c9af3222f918973b426ae349e9f614fb4de191e7807ec8193775a98cd,
35821bytes/974linhas. Teste97c26fbf permanece idêntico ao RED congelado.

1410relacionados nos9arquivos públicos passaram, incluindo195próprios,
0falhas/erros/skips,37,547s. As6sondas independentes passaram. Ruff src/tests
e lint restrito PoC limpos;372arquivos conformes no format; mypy strict
367arquivos limpos em cada alvo3.11/3.14. Runtime somente Windows3.11.3,
pilha64MiB no runner;3.14 é análise estática.13protegidos/app124 intactos.

Sob delegação, aceito a ponte SOMENTE como modelo puro/portas falsas.
Todos os6findings reproduzidos ficaram verdes antes da integração. Fonte
e teste podem ser publicados juntos, preservando o commit RED anterior;
o tip integrado não é mais a ausência deliberada do módulo. Isso não
autoriza SO real, cleanup físico, PG16, Docker, acesso a estado consumido
nem produção. As limitações e o próximo lote seguro estão em
PHASE-9-W1-ORACLE-DUPLEX-VALIDATION.md. Nenhum aval individual inventado.
