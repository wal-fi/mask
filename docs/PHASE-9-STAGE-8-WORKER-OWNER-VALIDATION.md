# W1 — owner privado do worker, sem integração operacional

2026-10-26. Implementado sob delegação após revisão do desenho e fechamento
do filho pelo Claude2. Novo runtime/worker_session.py: nenhum chamador no
gateway, bootstrap, MCP ou Admin; SQL PGWire continua recusada. Só fakes de
SO/transporte no Windows3.11.3, sem DockerCLI, subprocesso real ou banco.

O chamador confiável aplica o guard do controller antes dos secrets, reserva
token SESSION da mesma geração/snapshot e registra o handle antes de open.
WorkerProfile é interno; statement_timeout/max_rows devem vir dessa geração.
O filho também limita o prazo pela configuração recompilada e confere rows.
GuardFacts é fato local confiável, não token autenticado ou nova medição.
Uma thread principal/dedicada não daemon vive até reap; pool é proibido por
contrato. ObjetoThread+ident conferidos, apenas request_stop é cross-thread.

BudgetLedger.adopt_session é a única extensão do núcleo de créditos: exige
SESSION RESERVED e publica LIVE uma vez sob lock comum antes do spawn.
mark_live existente e custos/limites não mudaram. Não é ResumeThread/cota do
SO. Segundo owner, token de outro tipo e shutdown recusam antes de spawn,
sem liberar reserva do chamador/outro owner. close sem adoção recusa.

Spawn fixa sys.executable/-I/-B/-m, seis env públicas sem herança, close_fds,
um FD AF_UNIX/SOCK_STREAM, stdinPIPE vazio/unbuffered e stdout/stderrDEVNULL.
GUARD_READY compara PID/PPID/AS antes de INIT. Prazo12s começa antes de
socketpair/Popen; retorno tardio ou stop não recebe secrets. Popen que lança
sem entregar handle permanece incerto/HELD, sem declarar ausência de filho.
INIT é escrito não bloqueante em blocos16KiB, fecha pipe e confere closed;
OPENED HMAC usa compare_digest. Referências temporárias não ficam no handle;
sem promessa de zeroização Python nem SO_PEERCRED como identidade do filho.

Jobs sem fila, um por vez e sem próximo job enquanto resultado pendente.
ERROR correlacionado pode continuar só nas categorias do codec. RESULT
vazio→ResultReceiver/pin máximo→frameD113 exato→DONE exato→estadoRESULT.
Só então send_result_to encaminha chunks validados; não retorna frame/rows.
Envio completo+descarte/unpin permite próximo job. Descarte sem envio drena
e encerra. Falha de envio não tenta de novo; prefixo pode ter saído, sempre
validado/mascarado. Erros opacos mantêm capacidade; nenhum retry/reconnect.
Prazo de query vem de statement_timeout+10s, envio30s separado. Idle tem
margem250ms para envio; corrida de agendamento pode causar EOF fatal, sem
promessa de aceitação perto do limite. A leitura não faz overread/makefile.

Cleanup mata antes de tocar stdin, retenta kill/poll/wait em janelas curtas,
confere término por poll (waitpid no POSIX), pipes closed e FD -1. Só então
descarta saída/unpin e confirma release. Falha persistente/handle incerto
retém reserva. Não promete prazo absoluto de syscall do SO nem encerramento
instantâneo do backend remoto. Não há thread auxiliar criada pelo owner;
threads=True no modelo significa esse fato, não thread dona já terminada.

41testes focados verdes. Duas regressões novas de close sem efeito ficaram
vermelhas antes do fix e passaram após checagem closed/fileno. Cobrem INIT
máximo maior que pipe, fragmentação1/7/16384 e frame+DONE coalescidos,
Popen tardio/stop/erro, guard divergente/tag/EOF, duplicação de owner,
categorias recuperáveis/fatais, DONE ausente/adulterado/extra, frame errado,
envio falho e kill/poll/wait transitório/persistente. Fake Windows não prova
semântica Linux de FD/pdeath/spawn/reap; haverá sonda nativa revisada própria.

Primeira rodada39:36falhas/3pass por AF_UNIX ausente no fakeWindows e teste
de importador por substring que confundia _worker_session_state. Corrigidos
apenas os fakes e AST; depois9falhas eram fixture com job no índice do número
de colunas em vez do campo job. Após corrigir a fixture39/39; com as duas
regressões close,41/41. Não se atribui essas falhas à prova de SO.

Ruff/check e format src/tests:291arquivos; mypy strict alvos3.11/3.14 nos
291arquivos, sem erro. Não foi executado runtime3.14. Seleção ampliada em
andamento; nenhum gate integral/PostgreSQL/pacote novo declarado.

Whitelists agora admitem apenas worker_session como consumidor privado de
guard/protocolo/receiver/frame. Socket somente nesse owner além do filho,
com contraprova AST: um socketpair AF_UNIX/SOCK_STREAM, sem rede/escuta ou
makefile. HTTP/ssl continuam proibidos no runtime. Testes estruturais por
nomes/imports são guardas de arquitetura, não sandbox contra código hostil.

Revisão somente leitura do Claude2 sem bloqueador de segurança, condicionada
ao ajuste O1 de disponibilidade antes da prova nativa: espera pelo lock em
fatias250ms até o prazo do chamador, em vez de uma tentativa só. Duas
regressões (hold real500ms/open e close) falharam antes do fix; agora passam.
Terceira cobre close com resultado pendente. Close do receiver repete só
BUSY de lock dentro de um único prazo3s, sem repetir send/receive/mutação
incerta. Deadline/fault/HELD não são reinterpretados como BUSY.

Agora48testes focados aprovados. Acrescentados saída opaca que mantém pin e
HELD mesmo após close repetido, idle vencido, UTF8 inválido e controle variável
recusado após12bytes antes do body. 436relacionados de owner/separação/budget
passaram antes desses quatro casos. Ruff/mypy serão conferidos no resultado
final; primeira medição ampliada1259 teve1257pass/2falhas: whitelist budget
não reconhecia o novo owner (corrigida de forma exata) e short_unicode do
encoder ultrapassou40s. Isolado passou32,69s; causa da variação indeterminada,
sem aumentar prazo, alterar encoder ou ocultar a rodada reprovada.

Notas do revisor incorporadas como contrato para prova nativa: interpreter
do pai é o Python instalado/inventariado da imagem qualificada, acionado
com -I/-B; não vem de PATH/config do cliente. sys.executable é apenas seu
caminho herdado, não verificação criptográfica do executável. O futuro
entrypoint/sonda confere caminho e flags antes de secrets. Idle inclui o
tempo de envio ao cliente; perfil curto pode encerrar o filho durante envio,
e a próxima query falhará fechada. Margem250ms não garante agendamento.
Coalescência/exatidão estão testadas nos fakes; AF_UNIX real segue pendente.

Rerevisão do delta O1 e da cobertura ampliada concluída: sem bloqueador para
o desenho do procedimento nativo, não execução/produção. BUSY do receiver
usa acquire com timeout internamente, portanto não gira sem esperar no
colaborador real. Teste temporal do encoder fica registrado como sensível
a desempenho, sem causa da oscilação atribuída nem prazo alterado.

Seleção final13arquivos: **1266passed em75,70s**, sem falhas/skips, incluindo
o teste temporal antes reprovado. Ruff/check+format e mypy3.11/3.14 em291
arquivos limpos. A rodada reprovada1257/2 acima continua parte da evidência.
Pins finais:
- worker_session.py 568f532ffd5575cf22650edc7e589154bbf4d21154a76ab270aa75ef6e5a2dba
- budget.py 08f1330a86086ab3f2abd2d25b6c03208b0d0500a03c51402de4dbe8865257b4
- test_worker_session.py 3f4c3bc8ecd5b06876c5233fee16ba6c158f8f794a2fee4beb88346b8ac794c1

B-1 fim a fim/B-2/D-090/C1 e
prova de EOF/PID1/carga continuam abertos. DesktopOff, nenhum novo ambiente,
segredo real, quota/job, segundo escritor, commit/push/deploy ou serviço.
