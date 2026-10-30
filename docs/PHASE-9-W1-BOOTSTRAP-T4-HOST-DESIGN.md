# T4 — coordenador concreto e emergência, antes do código

2026-10-28, sob delegação; proposta de implementação para revisão. Componentes
puros e3cf9f4d/47testes aceitos pelo Claude2; transporte e6ca9e60/77testes
aceito. Nenhum DockerCLI/raiz/estado/comando T4 ou credencial novo executado.

## Reuso exato, sem invocar mains consumidos

Novo arquivo/entrypoint `docs/poc/w1_bootstrap_t4_run.py`, carregando por SHA
o módulo v2b59388f5 e seu original4bc0b083, **somente definições**, sem chamar
main/admit de roots consumidos. Nova classe Host herda v2.Host. Override
planejado explícito: __init__, pins, preflight, create_own, inspect_own,
perform_b, watchdog e cleanup_owned; nenhuma mutação dos módulos carregados.
Novo main/admit específicos e nova raiz Temp maskgw-oracle9-t4-<data>-<uuid>.
Não editar coordenadores, validadores, ciclo ou sampler congelados.

Continuam os mesmos objetos v2.save (journal12/replay), Base.start_cycle/
sample/checkpoint/observação/PS/CLI/restore_desktop/empty_inventory/write_new,
salvo wrappers explicitamente necessários para publicar posse. Os objetos
usados por herança e a lista de overrides serão testados. Se o código precisar
de outro override, declarar/revisar esse delta antes do uso real.

Init captura os6helpers históricos por SHA e a nova preparação/transporte,
os7Intents e suas linhas completas, antes de A. Estado fresh público/fechado
contém task/program/entry/pins e os comandos/medidas exatos; invocação xb
antes de A. Intents duráveis antes de cada create; comando vem da captura,
nunca de releitura durante cleanup. Fonte do estado é pública, sem seed.

Pins de execução validam fontes correntes, executáveis e contexto. **Pins de
cleanup** validam só executáveis/endpoint e integridade em memória do código
capturado; fonte pública alterada/ilegível aborta o lote mas não impede
identificar/limpar pela captura admitida. Nunca ignorar pin de docker.exe,
PowerShell, config/meta ou endpoint para tentar apagar recurso noutro daemon.

Preflight reutiliza perfil daemon/kernel/inventário vazio e admite imagem621
por ID com Config/RootFS exatos do candidate-image.json histórico pinado.
Sem tag mutável, pull/build/pip/cp/commit/exec. Medir custo dos pins no host
antes de A,≤3s; síncrono demorado não pode silenciosamente congelar heartbeat.
Se ultrapassar, abortar antes de Desktop/create, sem ampliar15s do watchdog.

## Execução sequencial e posse

Create retorna CID completo, que deve coincidir com a intenção pelo inspect.
Aceitação usa novo validador T4, sem stdinfalse histórico. Cleanup usa apenas
posse/Intenção/captura, labels próprios por subconjunto, tolerando metadado
extra; não perfil de aceitação. Uma intenção por CID, não reconstruída.

**Create indeterminado** (timeout/falha sem confirmação de CID/request):
ausência por nome em um instante não prova que o engine terminou a criação.
Não declarar release/restore só porque o inventário está vazio. Tentar resolver
a intenção exata para identificar recurso próprio, sem repetir create; se
continuar indeterminado, HELD e Desktop preservado, sem próximo caso. Registrar
pendência para recuperação específica. Sem retry de create/caso nem prune.

Depois do inspect, ManagedBootstrap adota CID e start. Só um owner/foreground
de attach por vez. Run supervisionado com heartbeat; wrappers não executam
qualquer SQL, produto, PG, listener ou segredo. Resultados passam pelo oráculo
fechado do caso; saída bruta nunca vira relato de sucesso. Seed público não
vai para estado/argv/log; mesmo sendo público, não criar logging/hash de seed.

No aborto, main cancela/aguarda foreground, quiesce (uma reavaliação3s se
necessária, sem novo start). Ticket só depois da coleta. Cleanup compartilhado
usa Lock único com aquisição limitada dentro do budget15s: primeiro prova de
ausência pelo CID; se já ausente, esta observação nova após ticket basta.
Se existe, inspect por posse→kill se vivo→reinspect→rm semforce→ausência nova.
Emite Absent apenas com ticket do próprio owner; close/assert_released antes
de próximo caso. Lock não adquirido mantém HELD, nunca executores concorrentes.
Se a emergência removeu antes, nenhuma observação antiga serve de recibo.

## Identidade do CLI pelo handle original

PID sozinho, lookup posterior por PID e comparação de commandline não bastam
para capturar identidade de nascimento: o PID pode já ter sido reaproveitado
antes do lookup. O main lerá FILETIME de criação com GetProcessTimes **no
handle original do Popen do Proactor**, ainda possuído pelo owner, e publicará
pid+FILETIME como inteiros exatos. Getter isolado, sem abrir novo processo por
PID nem fechar o handle emprestado; falha deixa identidade ausente/retida.
Acoplamento CPython3.11.3/stdlib pinados, com fakes antes de qualquer chamada.
Nada de uint64 passando por float/JavaScript. Nenhum GetProcessTimes foi
invocado por este documento.

Contrato Win32 conferido no [GetProcessTimes oficial](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes):
consulta pelo handle retorna FILETIME de criação; preservamos high/low32.

Comando PS de emergência é template fixo, só PID decimal e FILETIME decimal
validados. Obter Process uma vez, **forçar .Handle antes de ler StartTime**,
comparar StartTimeUTC.ToFileTimeUtc exato, e .Kill/.WaitForExit3000 no mesmo
objeto; Dispose no finally. Nunca Stop-Process -Id após conferir, nunca
obter outro Process pelo PID para matar. Categorias: KILLED, ABSENT,
IDENTITY_MISMATCH, ERROR; sem mensagem original. O comando completo e os
fakes voltam à revisão antes de execução.

A captura persistente de .Handle é deliberada: a [implementação Microsoft
de referência](https://github.com/microsoft/referencesource/blob/main/System/services/monitoring/system/diagnosticts/Process.cs)
liga Handle a OpenProcessHandle; GetProcessHandle/Kill reutilizam o handle
retido. Só usar o mesmo objeto sem forçar handle não basta para assumir isso.
É inferência para esse desenho; runtime real do host e caminho serão medidos.

## Watchdog e isolamento do loop

Thread não-daemon inicia antes de A; heartbeat1s, stale15s desde início do
monitor; depois B também prazo600s. Snapshot imutável sob lock, escrito só
pelo main: intenção/CID e, assim que disponível, PID/FILETIME original. Sem
referência ao owner/Process/transporte/tarefas asyncio no thread. Único sinal
ao loop é request_abort fechado/call_soon_threadsafe, ack≤2s quando vivo.

Emergência usa executores públicos síncronos delimitados, separados de
invoke do main; sem communicate com stdin/seed. Ordem: CLI próprio pelo
PS acima, depois cleanup de CID sob o Lock comum, com posse/ID. Nenhum
comando arbitrário/canal privado. I/O concreto também será revisto antes de
uso: argv fixo, ambiente allowlist, stdout público limitado e stderrDEVNULL.
Logs emergency-NN.json/xb com categoria/identidade/resultado, sem canário.

Se sem CID antes de B, só registrar/abortar, nenhuma ação sobre Desktop.
Se CLI ainda sem identidade, não inferir PID nem matar por nome; remoção do
CID impede start atrasado, mas não comprova que CLI foi recolhido. Main
continua obrigado a quiesce/ticket/nova ausência. Se loop não volta, HELD e
Desktop não restaurado. Watchdog disparado sempre NOT_PASSED. Event de stop
depois da restauração; join35s. Join falho também mantém pendência.

Fakes: arquivo fonte muda após create, label extra/profile drift, create
indeterminado, heartbeat16s, timeout global, PID reutilizado, handle original
emprestado nunca fechado, falta de posse, lock ocupado, emergencyremove antes
do ticket, nova ausência posterior, join falho, e nenhum objeto asyncio no
snapshot do thread. Prazos seguem a soma496<600 da proposta; sem relaxamento
em voo. Código ainda ausente, tudo antes da nova raiz/comando/execução T4.

## Precisões aceitas e calibragem antes de código operacional

P1 foi medido uma vez no filho Python base próprio, sem Docker: igualdade
exata de FILETIME, mismatch não matou, match matou/recolheu;1pass/1,45s.
Claude2 aceitou fatos; contexto/fuso/limites em IDENTITY-VALIDATION.

P2: captura síncrona imediatamente após start retornar **ou lançar com
processo adotado**, antes de qualquer outro await. P3: caminhos herdados
run_own/check_attestation/commit-own/copy-* devem ser inacessíveis no fluxo
T4 completo de fakes; se precisar de overrides extras, declará-los antes
do uso. P4: pins de cleanup também antes de cada comando do watchdog.

E1–E4 aceitos: reusar bounded58c em namespace/loop **próprios do thread**,
sem compartilhar dict/environment/mainloop/owner/seed/tarefas. Não usar
self.libs[bounded] no watchdog. Erro/limite/exitnãozero é ERROR/HELD, stdout
somente para parser fechado e nada cru no journal. Spawn desse helper fica
fora do wait_for; não cancelá-lo por fora nem afirmar prazo de spawn. Join
falho mantém HELD/pendência sem restaurar Desktop. Não é garantia genérica
do SO, conforme revisão e EMERGENCY-VALIDATION.

Após conferir baseline de rm6,297s, calibração proposta atual substitui os
30/35 e496 anteriores: executor45s/join50s, capsPS4/absence2/inspect2/kill4/
rm8; pins≤1s (amostra atual0,125s). Pior emergência24+7+10=41<45; ack2+
lock1+executor45+margem2=50. Main cleanup21/caso53/sete371+29matriz=400,
mais28 pendente+93restore+50join=571<600pós-B. Só planejamento antes de A,
sem alterar canal/worker ou inflar prazo de teste real após falha.

## Binding do coordenador — precisões antes do código

Lista atual de overrides será11: os8iniciais mais cli, run_own e
check_attestation. Esses dois últimos sempre recusam, cli chama diretamente
o BaseHost.cli e recusa commit/cp/exec/pull/build/image-rm/copy-* e comandos
fora do inventário T4. Isso elimina o gancho commit-own da v2 e o transporte
antigo de stdinDEVNULL. Teste de identidade dos demais métodos herdados e
fluxo inteiro com fakes antes de efeito real. Mudança só restritiva, sob P3.

record_intents herdado omite command: por isso cada intenção completa será
gravada em arquivo **xb próprio**, incluindo argv capturado, antes de create;
o journal mutável guarda status/CID. Não confiar só nesse journal para argv.
Main mantém mapa de Intents imutáveis, nunca reconstrói na limpeza.

Metadata do watchdog só depois de close com join positivo; no join falho
usar status fixo/HELD, sem ler campos em mutação. fired é Event independente.
Ack informativo, não impede emergência. Limitação L1: falha/mismatch do CLI
interrompe a limpeza externa; preservar pendência, sem executor novo/retry.

Caso retain mede retenção/CLI versus CID; SENT só comprova pipe local.
Recebimento e igualdade do corpo serão comprovados pelo relatório do caso
normal/negativo, não inferidos de CID ainda vivo. Shell/PG reais ainda terão
sua prova própria. Não acrescentar protocolo/ACK ou reescrever helper aceito.

Qualquer caminho com tarefas/owner incertos conserva Host/loop e ownership;
main não pode encerrar asyncio.run com spawn pendente. A integração deve
explicitar estado HELD e a retenção antes de ter entrypoint operacional.

Binding primeiro em w1_bootstrap_t4_host.py, sem main operacional. Lista12
overrides: os11acima e checkpoint, que arma o relógio pós-B **antes** de
delegar o checkpoint B, conservadoramente sem atrasar seu início. Save/journal,
start_cycle e sampler continuam herdados. Entry/admit/materialização/HELD-loop
serão revisados separadamente após esse binding e seus fakes, antes de A.

## Binding implementado, ainda sem entrypoint — 2026-10-28

Contrato de limpeza atual substitui a proposta de21s/53s acima antes de
qualquer execução T4: **22s de cleanup**, aquisição do lock limitada a1s,
caso54s; sete casos378s +22s margem =400s. Mantém28s pendente (duas
quiesce3s +22),93s restauração e50s join:571s<600s pós-B.

A ordem do main passa a ser **inspect por posse capturada primeiro**,
depois kill4/reinspect3/rm8 se necessário, e inventário por CID3s obrigatório.
Inspect inicial3 +kill4 +reinspect3 +rm8 +ausência3 =21s +lock1 =22s.
Cada timeout é recortado pelo mesmo deadline; não renová-lo entre comandos.
Inspect não zero só autoriza consultar ausência: nunca é ele próprio prova
de remoção. Falha/malformação/posse errada não autorizam mutação. O inventário
final bem sucedido e vazio é sempre novo, depois do ticket, inclusive quando
o watchdog já removeu o CID. Esse ajuste reduz um comando redundante no
caso normal sem abandonar o requisito de ausência posterior ao ticket.

O oráculo retain exige CID ainda vivo no primeiro inspect após quiesce,
somente no caminho de teste. Recuperação final não repete esse oráculo nem
sobrescreve a evidência xb. Registro removed sem owner fechado ainda exige
ausência nova e close; não pula a obrigação lógica por remoção física.

Tarefas de heartbeat, foreground, start cancelado e drain passivo são
registradas antes do próximo await. Falha de criação fecha a coroutine que
não foi submetida; assert final verifica todas as tarefas do host, além das
do owner. Namespace v2 capturado também tem seu hash rechecado.

29 testes de binding passaram com CLI/processo/monitor simulados, incluindo
os sete casos completos, identidade imediata no start falho, ausência após
remoção externa, falha de inspect, posse errada, perfil alterado, create
incerto e deadline único. Não é ainda teste do entrypoint com start_cycle
completo: ele continua ausente, assim como raiz/estado/comando operacional.

## Ajuste B1–B3 da revisão, antes da execução

Primeira versão do binding foi rejeitada por três oráculos. Flood passa a
observar somente owner.fault do pump com prazo2s, sem drain do produtor
infinito. Relatórios normal/negativo usam4s para observação EOF e saída CLI;
não reduzir a fonte e3cf aceita. Retain exige inspect0 e CID vivo, senão
reprova mesmo que a ausência posterior permita liberar na limpeza final.

Soma atual substitui54/400/571: caso56s, matriz414s (392+22margem), pendente28
+restore93+join50 =585s<600. Nenhuma T4 foi executada, nenhum prazo inflado
em voo. Três regressões vermelhas primeiro;32fakes finais verdes. Posse e
troca inspect-primeiro aceitas pelo reviewer; delta de oráculos em revisão.
