# W1 — canal privado de bootstrap, código e fakes

2026-10-28, sob delegação. Incremento apenas em docs/poc e testes; nenhum
produto, dependência, imagem instalada, listener ou ingresso operacional
alterado. Ainda em revisão de código pelo Claude2. A direção/contratos e R1
foram revisados antes do código/fix. Sonda nativa T4 obrigatória e não feita.

## Escopo e contrato

`docs/poc/w1_bootstrap_channel.py` não tem main/efeito no import. Só aceita
papéis P/C e CID/task/imagem/fonte públicos exatos; comando fechado
docker --context desktop-linux start --attach --interactive CID. Runtime
Windows-I-B sem otimização, CLI/config/meta pinados, ambiente allowlist e
stderr descartado. Nada disso foi invocado contra Docker neste incremento.

Seed autod delimitado16+corpo1..16384+trailer8, máximo16408bytes; reader Python
os.read exato com prazo não espera EOF e só recusa sobra já visível, sem
afirmação eterna de canal quieto. READY canônico ASCII512bytes inclui LF e
identidades esperadas; stdout32KiB incremental, sticky erro com drain/discard.
Input, output e repr permanecem privados; dados só por métodos reveal explícitos.
O canal não valida sucesso de aplicação, apenas transporte/fechamento.

Um owner/loop e uma operação pública por vez; tarefas registradas antes de
await e deadline absoluto de abertura/envio12s. PGsetup60/attach300 e controller
120 são limites a cumprir pelo coordenador ao chamar retain/drain; não são
um watchdog independente do container. Reap/close3s separados, sem promessa
para syscall que não retorna. Falha/limite não aproveita prefixo de sucesso.

## R1 — vermelha antes da correção

Primeira matriz medida: **15pass/1fail**, a corrida de spawn tardio. Um CID
era observado parado, docker start terminava depois, e o draft liberava o
canal ao recolher só o CLI. Nenhum recurso real envolvido. Desenho R1 revisto
pelo Claude2 antes do fix: quiesce irreversível, resolve spawn/reap/pipes/pumps,
ticket público único por owner; coordenador remove CID e confirma ausência
posterior ligada ao ticket, então close. Não aceitar Stopped nem ticket de
outro owner; observação revogável de parada não é suficiente.

O teste final mantém o cenário: spawn tardio inicia CID simulado, CLI é
recolhido e seed nunca enviado; release continua falso até ausência externa.
Quiesce pendente mantém HELD, sem cancelar spawn nem emitir ticket. Sucesso
natural também passa pela mesma ordem. Tickets são fatos do coordenador
confiável, não atestação de SO. Nenhum DockerCLI é feito pelo cleanup helper.

## Medições Windows3.11.3, somente fakes

- **50 testes aprovados**,2,35s na primeira matriz final: codecs/limites,
  reader exato/semEOF/IO/timeout/sobra, READY fragmentado/inválido,
  nenhum envio antecipado, saída excessiva/drenagem, erro após prefixo de
  sucesso, registro de cada tarefa, falha stdin write/drain/close/wait_closed,
  feed bloqueado, kill transitório/persistente, spawn tardio/pendente,
  ticket anterior/alheio, fechamento idempotente, PG retido e loop sem tarefas.
- Mypy strict do teste com alvo3.11 aprovado; Ruff integral do teste e lint
  E9/F63/F7/F82 do helper aprovados. Não declarar helper tipado estritamente.
- Os testes usam watchdog independente8s, sem alterar prazo3s de produto/helper.
  Nenhuma conexão, seed privado real, DockerCLI, CID, rede ou PostgreSQL novo.

Histórico preservado: uma rodada de teste ficou presa porque o teste de
registro de tarefa perdia o owner após uma exceção esperada. Pytest próprio
foi identificado por PID/parent/caminho/comando e encerrado; só esse processo
foi tocado. Corrigido o harness para guardar owner antes de start e recolher
as tarefas; acrescentado watchdog. Outra rodada marcou49pass/1fail por exigir
três janelas250ms dentro do budget fake80ms; o cenário de kill usa850ms,
inferior ao3s real, sem mudar limite do helper. Repetição50pass acima.
As falhas iniciais de Ruff/mypy do teste foram corrigidas antes da revisão.

## Limites e próximo passo

Ainda não provados asyncio/Proactor, Docker stdin/EOF, kill CLI versus CID,
perfis OpenStdin/StdinOnce ou framing no container real. Nenhum segredo pode
usar o canal antes de T4. Próximo: revisão de código/fakes e correção de
findings; depois desenho/fonte/perfil/estado/comando da sonda pública T4,
com ciclo novo revisto antes de A. Não repetir mains/raízes consumidos.
Não é prova W1+PG16, B-1/B-2/D-090/C1, serviço, release ou produção.
SQL PGWire continua recusada. Sem commit/push/job/segundo escritor.

## Revisão adversarial B1/B2 e delta

O Claude2 rejeitou o draft439d0e67 por dois bloqueadores: erro pegajoso de
wait_closed/read impedia ticket para sempre; _until absorvia cancelamento
do chamador e impedia o aborto de drain. Ambos reproduzidos antes do fix:
seleção7casos=**5fail/2pass**. A forma do fake foi então alinhada ao stdlib
real e os mesmos5 casos continuaram vermelhos. Um caso adicional cancelando
o fechamento do stdin depois de write também falhou antes da correção:
registrava SENT em vez de UNKNOWN.

O contrato estreito da correção foi revisado antes do delta. Não aceitar
qualquer exceção como prova de handle fechado. O helper depende explicitamente
do CPython3.11.3/Proactor do host, com6 arquivos stdlib pinados por SHA, além
de CLI/config/contexto. PipeHandle real **não** tem atributo closed: tem
handle, que se torna None após CloseHandle. Essa forma foi conferida no fonte
local e numa unidade Windows com dois handles reais, abertos e fechados,
sem subprocesso/Docker/rede. Fakes reproduzem handle, não um closed inventado.

Após processo recolhido, a prova positiva para fd0/fd1 exige transporte não
nulo, get_extra_info("pipe") de tipo exato PipeHandle e handleNone. Falha ou
atributo/tipo desconhecido mantém HELD. Isso também é exigido no caminho
normal antes do ticket. _stdout_eof continua necessário para sucesso de
drain; fechamento físico com IO permite só cleanup, mantendo a categoria.
O acesso privado Process._transport é deliberadamente específico do harness
pinado, não uma API pública portátil. T4 deverá confirmar no attach real.

_until propaga CancelledError quando current_task.cancelling()>0; cancelamento
da tarefa própria é distinguido. Wrapper libera busy em finally e cancelamento
torna o owner irreversivelmente HELD/quiescing. Tarefas internas continuam
adotadas/shielded; coordenador cancela/aguarda seu foreground, quiesce,
remove CID/observa ausência ligada ao ticket, close. Nunca volta a confiar
em Stopped anterior. Spawn tardio e pipe incerto continuam sem release.

Metadata agora registra seed_delivery=NOT_SENT/SENT/UNKNOWN. UNKNOWN começa
antes do write (que pode entregar parcialmente) e permanece em erro/cancelamento
de envio; SENT significa apenas handoff completo ao pipe local do CLI, não
receipt do container. Cancelar antes do write deixa NOT_SENT e nunca envia
posteriormente; cancelar durante write/drain/close deixa UNKNOWN.

Matriz do delta: **72pass**,2,41s; inclui cancelamento de start/send/drain/
quiesce, cancelamento da tarefa interna, antes/depois do write/close,
handle alheio/aberto, wait transitório/persistente e6pins do stdlib. A primeira
unidade PipeHandle recebeu WinError5 dentro do sandbox; repetição fora dele
aprovou, sem skip e sem afrouxar teste. O teste de read foi corrigido para
acordar a leitura anterior antes de injetar a falha; a primeira injeção não
tinha exercitado esse caminho. Nenhuma mudança de prazo do helper.

Alvo atual do delta para revisão: helper
`cdf381ee49faf99c6aa9bda63c0ec5f2e15e52f619cb287f2ebbbb735594a121`;
testes `18e16c21e5576bc2d9a5014cab184d3f2d1921f53de31493562789a86886966e`.
A seleção relacionada anterior ao delta aprovou591 em48,38s; não atribuir
esse número ao código do delta. Ruff/mypy do teste corrigidos antes da
revisão final. Nenhum DockerCLI ou credencial neste incremento.

## Fechamento L1 após aceite do delta

Claude2 aceitou cdf381ee (B1/B2/R1 resolvidos) e recomendou esperar os
callbacks de fechamento dentro do mesmo end. Teste primeiro:2casos fd0/fd1
falharam antes, pois o callback físico ocorria20ms após EOF. O delta final
gira o loop e reavalia os dois handles e as tarefas no mesmo orçamento3s,
sem renová-lo, nunca usando is_closing como prova. A flag de stdin pode ser
confirmada pelo handle positivo depois de um wait_closed falho. Se não fechar,
continua HELD. Diagnóstico de spawn agora é SPAWN, sem ser coberto por IO
genérico; teste de runtime/spawn e filtro de ambiente acrescentados.

**77pass**,3,57s; helper
`e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a`,
teste `94a127be1320292273f402e18bd7777a488877385e73b3a0bc4665ad1e895b1a`.
Seleção no delta anterior cdf381ee:613pass/41,49s, sem atribuí-la ao L1.
L1 e diagnóstico final enviados para revisão somente leitura. T4 não feita.

Claude2 aceitou e6ca9e60/77focados, sem bloqueador. Seleção final sobre esse
helper: **618pass/47,94s**, nenhum skip/falha/erro. Ruff integral src/tests,
format301arquivos (inclui helper), mypy strict3.11 e3.14 em300arquivos verdes;
lint restrito do helper verde. Runtime executado sóWindows3.11.3. git diff
--check aprovado; avisos LF→CRLF não são falhas. Nenhuma suíte com DB ou
pacote instalado foi alegada neste incremento sem produto alterado.

Próximo é a sonda pública T4, com plano/código/estado/comando revisados. Direção
aceita; contratos do watchdog/oráculos complementares enviados à revisão.
Sem DockerCLI/secret/novoPG/commit/push/job ou outro escritor neste fechamento.
