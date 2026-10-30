# loaded-as128 — supervisor, desenho antes do código

**2026-10-22 — proposta sob delegação, sem implementação/execução deste lote.**
Produtor/coletor anterior:136 novos/610 relacionados, revisão Claude2 sem
bloqueador no código com fakes. Não reinterpretar como medição Linux ou
contenção. AS32 e as seis rodadas anteriores continuam preservados.

## Escopo e arquivos

Novo docs/poc/linux_loaded_probe.py: composição do supervisor/membro, canal
incremental e backend Linux. Testes novos em tests/test_loaded_memory_supervisor.py,
só fakes: sem construir o backend real, abrir /proc, alocar payload, iniciar
processos, Docker, banco, SQL ou serviço. Não editar scripts congelados nem
o core/collector/membro salvo finding acompanhado de regressão/revisão própria.
Sem novo host observer, preflight executado ou comando de carga neste lote.

O entrypoint novo será executável em tese, mas nenhum uso real está autorizado
por esta preparação: código/testes, integração do host/inspect e comando terão
revisão antes de qualquer rodada. Não há consumidor de src ou configuração de
produto. B-1/B-2/D-090 gate2/SQL/produção continuam abertos.

## Composição e argumentos fechados

Supervisor aceita exatamente --case control|private|shared --expected -|digest
conforme parse_case_args do core. Membro aceita --member case exato e nunca
recebe o digest. Entrypoint só Linux isolado/no-site, UID65534; supervisor PID1,
membro pid>=2/ppid1. Importar o arquivo em testes não abre recursos.

Carregar os cinco helpers por spec com nomes já aprovados e arquivos irmãos
exatos: _lab_loaded_protocol/member/collect, _lab_import_probe e _lab_support.
Não criar nova exceção de origem, wildcard ou caminho por argumento. Os nomes
não precisam ser inseridos no cache (ausência é permitida no coletor anterior).
Todos os helpers são carregados igualmente em cada membro antes do baseline.
No membro, carregar manifest runtime.json limitado (owners/generated) e
inserir só /installed antes do callback fixo dos três ROOTS. Sem DSN/secret.

## Backend de supervisor e ownership

Factory real gated antes de imports Linux/processo. Seam privado de APIs
confiáveis só para testes. Deadline absoluto20s capturado antes de carregar/
preparar/criar o membro, sem renovar por etapa. Todo I/O usa saldo e sinal
STOP; clock não finito/regressivo e interrupção são falha. Não prometer teto
absoluto para syscalls travadas; watchdog externo30s continua gate separado.

Antes do spawn conferir PID/UID/flags, NNP/caps, cgroup raiz, memória externa
192MiB/swap0/pids16, glibc2.36, thread1, fds012 e inventário só PID1. Preservar
snapshot inicial de VM/cgroup/AS. Controle exige AS herdado ilimitado;128
exige VmSize<=124MiB e hard compatível, seta soft=hard128 **antes** de Popen,
confere de volta. Não elevar cap depois de falhar nem restaurar hard infinito.

Uma única criação Popen, argv exato python -I -B -S /probe/linux_loaded_probe.py
--member case, close_fds=True, bufsize0, stdin/stdout PIPE, stderr DEVNULL,
env fechado só PATH=/usr/local/bin:/usr/bin. Guardar ownership do Popen
imediatamente antes de configurar canal/fds. Falha parcial ainda recolhe só
esse filho. Sem preexec_fn, thread, socket ou processo extra.

Canal próprio preserva **bytes crus**, não reserializa held: linhas<=4096,
buffer<=8192, leitura incremental inclusive vários eventos por read, EOF só
com buffer vazio. Prefixo/sufixo parcial/linha extra não vira EOF limpo.
Writer não bloqueante trata parcial/EAGAIN/EINTR com select e mesmo prazo.
Antes de enviar comando exigir canal quieto (sem bytes já pendentes); não
ressincronizar. Reusar decode_line antigo e core.decode_held (este<=1024).
Nenhum stdout de diagnóstico até o relatório final pequeno do supervisor.

## Leituras independentes e fluxo

Observe lê /proc/<pid>/status e limits limitados, PPid=1, threads1; usa parser
novo de status/limits, não inventa VM do pai para o filho. Lê fds/links e
children do filho (children opcional ausente como no helper antigo); exige
012+um statusfd, sem sockets/filhos, comparando com cada end do membro.
Inventário global vem do helper antigo (/proc **e** cgroup) para {1,pid}.
Guardar cgroup por ponto: memória/stat/events/peak/pids. Qualquer aumento
max/oom/oom_kill, pico externo>192MiB ou counter regressivo invalida antes
do próximo comando e no final. Anon e shmem não são somados a file.

1. Após spawn, ready tem envelope fechado/pid próprio/ppid1, limits e VM
   válidos. Observar o filho independentemente antes de core.ready/GO_IMPORTS.
   Limites declarados e observados iguais; em128 ambos respeitam cap/folga.
2. Consumir somente baseline/start/module/end012/verified pelo ImportCollector.
   Em cada end conferir também observe/fds/limites/VM independentes. Só fluxo
   completo expõe snapshot. Depois ler loaded com envelope fechado, observar
   novamente e conferir limites/picos do membro e observado.
3. core.admit_imports recebe snapshot auditado e fatos observados, calcula e
   compara digest esperado **antes** de PRESSURE. Preparar inventário comprimido
   limitado nesta fase, nunca reconstruí-lo no membro após OOM.
4. Observar novamente antes de cada core.pressure e enviar exatamente seus
   bytes. Receber held cru, core.held valida/classifica candidato. Observar
   plateau independente com payload retido; core.release exige pico igual e
   usa anon/inventário reais antes de enviar RELEASE_PRIVATE/SHARED.
5. released deve ter só phase/kind corretos. Observar e chamar core.released;
   no controle privado aplicar até5 amostras/1s via release_wait/release_sample,
   sempre observações diretas, sem novo comando ao membro ou liberar shared
   antes de comprovar ambas condições de descarte. Prazo não é renovado.
6. core.finish -> FINISH -> done fechado -> EOF **real** sem resto -> wait
   usando saldo. Ainda não exportar resultado/digest. Reap/fechar ambos pipes,
   inventário final só PID1 e cgroup final sem pressão. Só então completed,
   e control_digest somente no controle DONE e dentro do prazo.

IO/parse/estado/callback/deadline inesperado é categoria fechada, sem cadeia
ou mensagem original, e interrompe comandos. Nunca enviar RELEASE/FINISH
depois de ABORTED; cleanup mata/recolhe, não declara descarte positivo.
Reusar reap antigo, só a lista do filho próprio, graça de2s e tentativa de
fechar todos os pipes. Cleanup incerto invalida, mesmo que wait tenha passado.
Fail/sinal/timeout/pressão externa interrompem o lote futuro no host.

## Resultado e testes antes de execução

Relatório próprio profile=loaded-as128, total_memory_contained=False,
outcome control_ok/imposed só após completed e cleanup real. Sem fits_as32.
FAIL do core preserva motivo; cleanup/pressão externa incertos prevalecem
inconclusive. MEMORY/IMPORT durante imports de128 só vira incompatible se
evento/código72/73 concordarem e cleanup confirmar; OTHER/audit/check/protocol
não viram imposição. Códigos divergentes (inclusive cleanup override77)
invalidam a interpretação da categoria original. Registrar não executados
é responsabilidade do futuro host, não iniciar automaticamente próximo caso.

Inventário usa pack_inventory antigo, relatório<=64KiB. Limite/erro de
serialização remove qualquer sucesso/digest; fallback fechado inconclusive.
Só metadados/linhas de módulos/VM, nunca dados do banco ou erros livres.

Testes primeiro com core/collector reais e I/O fake: três caminhos completos,
comparação de digest antes de comandos, falhas em cada fronteira, fds/picos/
limits/PPid/inventários, origem/marcadores forjados, descarte/amostras/clock,
EOF parcial/extra/wait/cleanup/cgroup, uma criação apenas e nenhum comando
após falha. Fakes de select/read/write/Popen/filesystem/getrlimit/setrlimit
provam ordem e ownership, não OS. Confirmar argv/env, captura antes de canal,
limites de linhas/buffers/relatório e construção parcialmente falha.

Próximos gates: revisão deste código e testes, depois host observer com novo
perfil/argv/inspect e procedimento preflight, depois comando exato e só então
rodada única separada. Nenhum commit/push, deploy ou liberação de produção.

## Revisão do desenho antes do código

Claude2, sessão51ea0d85, sem bloqueador de composição condicionado a R1–R4:

- R1: /proc/<pid>/fd e readlink do filho são dependência nova de acesso
  ptrace/perfil do container. Permissão negada/falha torna inconclusive,
  **sem** fallback aos fds declarados. A primeira execução real deverá
  qualificar essa interface; fakes não a demonstram.
- R2: só a linha imediatamente após PRESSURE segue crua para core.held,
  conferida<=1024 antes da chamada. Restante usa decode_line. Held fora
  dessa fase, outra linha no seu lugar e quiet com buffer/select legível
  são PROTOCOL. Testar reads agrupados/held grande/held antecipado.
- R3: precedência fechada: cleanup/final_inventory incertos -> inconclusive;
  pressão externa -> inconclusive; código espontâneo divergente do esperado
  -> inconclusive; OBSERVED_FAIL -> fail; MEMORY/IMPORT de128 com72/73 e
  cleanup concordantes -> incompatible; DONE completo -> control_ok/imposed;
  restante inconclusive. Falha contém só stage e category de enums locais.
  Após aborto do core não se espera saída natural0: kill/reap é cleanup
  obrigatório e seu código não é interpretado como recusa ou sucesso.
  Deve-se registrar separadamente a ausência de saída natural esperada,
  nunca mapear um sinal a MEMORY. Esse detalhe aguarda conferência abaixo.
- R4: observe obrigatório depois de ready, cada end, loaded, antes de cada
  PRESSURE, no HELD, em cada amostra de descarte. Cada observe confere status/
  PPid/threads, limits, mesmo fd set, children/inventário e cgroup. Counter
  regressivo/fd divergente interrompem antes de outro comando.

Refinamento R4 ainda em conferência: leitura **depois** de done não pode ser
condição positiva com o membro atual. run_member emite done e imediatamente
fecha seu statusfd no finally e retorna; o filho pode já ter saído/zumbi
quando o pai lê a linha. Proposta: última leitura independente enquanto o
membro está bloqueado em FINISH, **antes** de core.finish/comando; depois
de done exigir só EOF/wait/reap/inventário/cgroup final. Sem ACK novo,
exceção a erro de leitura, fallback ao membro ou condição de corrida para
aprovar. Confirmar esse contrato com o revisor antes de implementar.

Pico igual pode dar falso inconclusive por pequena alocação entre amostra do
membro e observação; preservar a regra, não inferir bug ou relaxar após medir.
Supervisor também tem AS128; pack/JSON/leituras podem falhar. Isso não fecha
contenção total nem garante recuperar todo OOM. Relatório final precisa
writer não bloqueante no saldo do mesmo deadline; nunca emitir sucesso após
cap/erro de serialização ou se a escrita terminar fora do prazo.

### Conferência R3/R4 concluída antes do código

Claude2 aceitou o R4 revisado: leitura completa final em FINISH_READY antes
do comando, **não** depois de done. Early exits de imports/audit/check também
não admitem leitura posterior estável: EOF/wait/reap/final bastam para
qualificar a falha, nunca sucesso. Isto substitui explicitamente a proposta
de leitura depois de done; não se implementará esse acesso racy.

N1 obrigatório: OBSERVED_FAIL só vira fail com observação independente
**antes do kill**, soft=hard128 e VmPeak>128 ou VmSize>=pré-pressão+40MiB.
Pico ou accepted alegado só pelo membro não prova FAIL. Falha da leitura,
ausência de confirmação ou sinal espontâneo produz inconclusive. Não chamar
core novamente depois de ABORTED; a confirmação adicional é só coleta de
fatos, nunca RELEASE/FINISH. N2: incompatible por72/73 só nos dois casos128;
import failure no controle ou74 sempre inconclusive.

Tabela final:1 cleanup/inventário/pressão externa incertos -> inconclusive;
2 exit natural divergente ou sinal não causado pelo próprio kill ->
inconclusive;3 FAIL confirmado conforme N1 -> fail;4 import72/73 em128 com
exit/cleanup concordantes -> incompatible;5 completed/DONE -> control_ok/
imposed;6 restante inconclusive. Cleanup registra se kill próprio foi
efetivamente chamado com sucesso; só SIGKILL compatível é atribuído a ele,
nunca classificado como recusa. Cobrir todas as linhas em testes.

Contrato apto só a testes primeiro/implementação com fakes. Sem aprovação
de código ainda, nem integração/host/carga/produção.

### Revisão do código: S1/S2 substituem os trechos iniciais correspondentes

S1: end012 **não** é ponto estável para fd/readlink do filho: a importação
seguinte pode abrir arquivo antes da leitura do pai. Nessas três janelas,
observe mantém status/PPid/threads/limits/inventário/cgroup independentes,
mas registra fds=None, sem listar/comparar descritores. O collector continua
exigindo os relatórios de fd do próprio membro nos ends. Checks de fd exato
independentes só em ready, loaded, pré-PRESSURE, HELD, released/amostras e
pré-FINISH, quando o membro está bloqueado. Sem fallback a fds declarados.

S2: a medição continua limitada a20s, sem renovação. **Depois** de cleanup/
checagens finais, somente a emissão de até64KiB tem orçamento fixo próprio
de2s, dentro do watchdog externo30s. Não executa leitura/pressão/comando novo
ou transforma timeout em sucesso. Timer do relatório ignora STOP apenas
para tentar preservar o diagnóstico, sempre não bloqueante e limitado.
Se esse canal também falhar, o processo sai70 sem traceback/fallback
bloqueante. Isto substitui a emissão sob o timer de medição proposta acima.

Relatório pode se aproximar de55–60KiB com inventário de43,7KiB e observações;
cap64KiB/fallback inconclusive permanecem, sem digest no fallback. Teto de24
observações é defesa de tamanho, não margem certificada de memória. A nova
rodada, se autorizada por revisão própria, deverá registrar o tamanho real.
