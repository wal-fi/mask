# W1 — loop privado do worker, sem chamador operacional

2026-10-26. Implementação sob delegação, desenho WORKER-SESSION-PLAN e
codec v2 revisados. Não liga PGWire/MCP/Admin nem cria worker no bootstrap.
Nenhum DockerCLI, banco, segredo real, instalação ou artefato novo executado.

O entrypoint worker_process exige guard Linux antes de ler secrets/ambiente
ou emitir READY. Exige -I/-B, optimize0, ambiente exato de seis entradas,
stdin pipe e um socket AF_UNIX já conectado/herdado. Sem bind/connect/listen,
makefile, processo/thread auxiliar, stdout/stderr ou nova resolução de DNS.
O pai futuro ainda deve fixar o interpretador/argv; checar flags no filho
não desfaz imports anteriores e não autentica o peer pelo SO_PEERCRED.

INIT é limitado e lido por readv em blocos16KiB, exige EOF do pipe e prazo
absoluto. Snapshot reconstituído, nonce/HMAC conferíveis no pai, uma conexão
e baseline S1 antes de OPENED. Jobs sequenciais usam o pipeline D-118 e S1
antes/depois de sucesso ou erro recuperável. RESULT vazio/frame/DONE só
depois dessas checagens. Falha parcial de envio nunca produz segundo ERROR.
Sem retry, reconnect, reset, fila ou reparo de estado. EOF/idle entre jobs
encerra; EOF parcial é fatal. I/O bloqueado no driver depende do pai para
kill/reap; pdeath não substitui prova de namespace/EOF ou remoto encerrado.

57testes com fakes no Windows3.11.3, incluindo INIT65644bytes fragmentado,
deadlines, shape/ordem, dez categorias de job, S1 divergente, envio parcial,
close uma vez e recusa de flags. As quatro contraprovas de -I/-B/-O falharam
antes do fix, depois passaram. Não é medição de SO Linux ou PostgreSQL.
Revisão inicial aceitou condicionada à checagem dessas flags; delta final
e whitelists estreitas seguem para conferência somente leitura do Claude2.

Revisão final desse delta concluída: sem bloqueador para implementar o pai
privado, que terá revisão própria. A inspeção AST é por nomes locais e não
prova transitivamente todos os colaboradores; RawChannel continua o
transporte já revisado. Não se interpreta esse teste como sandbox Python.

Seleção ampliada de12arquivos:1217coletados e todos aprovados (exit0), sem
skips. Inclui os núcleos de frame/encoder/receiver/créditos, job/S1/guard e
separação de planos. Ruff/check e format em src/tests:289arquivos limpos;
mypy strict alvos3.11 e3.14 nos289arquivos, sem erro. Só runtime3.11.3 foi
executado nesta seleção; não representa suíte integral/integração PostgreSQL.

Whitelists alteradas explicitamente: test_worker_job, test_worker_protocol,
test_linux_process_guard e test_result_frame admitem só worker_process como
novo consumidor privado. test_plan_separation permite socket só nesse
arquivo e exige AST socket.socket(fileno=...), sem APIs de rede/escuta.
HTTP continua proibido; não se generalizou exceção de rede a runtime.
Os hashes anteriores desses testes continuam históricos, não atuais.

Limitações: erro antes de INIT válido fecha sem ERROR; corrida de idle com
primeiro byte pode encerrar conservadoramente; close bloqueado é recolhido
pelo pai futuro. Não há owner, pin/DONE no pai ou prova de cleanup físico.
B-1 fim a fim/B-2/D-090/C1 continuam abertos; SQL continua recusada.
Sem commit/push/deploy, quota/job novo ou segundo escritor. DesktopOff.

Pins:
- worker_protocol.py cd6b3123ba0137ec85ff7d12d7fcefca3ff2b2168200c99a3cddde3e6d21fd09
- worker_process.py 91c353b58f0d95c16eb74822d3a748e7efd6761ed08388a38f5abfbaf8d734bb
- test_worker_process.py a1d41ef6f7f229325d495359dbe56253c8a7940bd5f3fbfff67fe562609e3ecd
