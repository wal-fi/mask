# W1 — T4 pública no attach Windows, proposta antes do código

2026-10-28, sob delegação. Transporte e6ca9e60 aceito pelo Claude2 com77casos;
nenhum Docker novo executado. Sonda obrigatória antes de credenciais e PG16.
Este documento é proposta para revisão, não evidência nem comando autorizado
por um revisor. A delegação do usuário permanece, com revisão antes de efeitos.

## Resultado e isolamento

Medir asyncio/Proactor Windows3.11.3 pinado → docker start -ai → stdin/READY/
frame/EOF/saída → recolhimento → quiesce/ticket → remoção/ausência/close.
Só canário **público fixo**, sem senha/HMAC/chave/PG/consulta/cliente. Não prova
W1+PG, isolamento de memória, B-1/B-2/D-090/C1 ou disponibilidade de serviço.

Imagem fixa621cc7f702ec34d7014809411fda7fc89ab6b95f6dc7d16315274d4a7006ef0b,
atestaçãof0c3cd54 e Config/RootFS exatos da rodada instalada; readmitir só por
inspect, sem pull/build/install/cp/commit. Não repetir roots/mains consumidos.
Uma rodada nova, nomes/task/CIDs próprios e intents antes de create. Nenhuma
rede nova: networknone, sem publish/hostports/binds/volumes. CIDs sequenciais,
removidos/ausência/close antes do caso seguinte; só um attach por vez.

Perfil proposto dos canários: rootRO, cap-dropALL, NNP/seccomp padrão,
memória128MiB/swap0, pids8, CPU1, core0, nofile128, restartno/logdriverNone,
TTYfalse, OpenStdintrue/StdinOncefalse, workdir/entry/Env exatos da imagem.
UID/GID10001 para papelC,70 para um papelP simulado na mesma imagem Oracle.
O papelP **não** representa PG/Alpine/shell, só transporta seu framing/UID.
Sem AS do worker ou novo mount: ensaio de pipe, não contenção de memória.
Fonte pública em argv via bootstrap que limita/descomprime/verifica SHA antes
de compile/exec; create inteiro medido≤26000. Fonte, helper e estado pinados.

Posse não é aceitação: cleanup exige CID/nome/task/imagem/comando e labels
próprios; não exige OpenStdin/perfil para remover recurso próprio conhecido.
Aceitação confere perfil completo separadamente. Não presumir label Desktop
herdado da imagem no CID; são3labels próprios, imagem tem4labels fixos.

## Matriz finita proposta

1. **Controller normal:** READY canônico com UID/PID reais; envia corpo
   público16384bytes, incluindo trailer no corpo; reader os.read do helper
   mede frame correto e emite resposta JSON fechada. Sem aguardar EOF para
   interpretar frame. Medir EOF imediatamente visível como booleano, sem
   exigir que exista ou que nunca chegue. Saída/exit0, drain completo.
2. **RoleP retido + cancelamento:** UID70, READY/frame, PID1 fica vivo depois
   de receber o canário. Host retain, inicia drain passivo, cancela/aguarda
   esse foreground; quiesce recolhe CLI. Inspect deve mostrar CID ainda vivo
   para provar que killCLI não equivale a killCID; então kill/reinspect/rm/
   ausência/close. Se CID terminar, registrar caso reprovado, sem inventar prova.
3. **READY incorreto:** source esperado divergente, sem seed enviado;
   erroREADY, quiesce/remover/ausência/close. Não tornar essa divergência
   aceita pelo validador de posse; a fonte/comando reais continuam admitidos.
4. **PID1 não lê stdin:** READY correto, corpo público máximo. send tem12s
   desde abertura: registrar SENTlocal ou UNKNOWN/DEADLINE conforme buffering
   real, sem afirmar recebimento pelo container. O objetivo é medir limite de
   espera e cleanup, não alegar que16KiB necessariamente lota todos os pipes.
   Quiesce e CID vivo/remover/ausência; nenhum aumento de frame ou prazo.
5. **Saída excessiva:** depois de READY/canário, PID1 escreve blocos públicos
   indefinidamente. STDOUT_LIMIT pegajoso, buffer retido0 e pump drenando;
   cancelar/aguardar foreground se necessário, quiesce e remover/ausência.
   Se o erro surgir durante send em vez de drain, preservar fase real na
   evidência; nunca aproveitar prefixo de sucesso.
6. **Cancelamento de start:** task de foreground cancelada depois de o
   spawn próprio estar registrado, antes de qualquer send. Spawn shielded
   continua adotado; quiesce limitado recolhe spawn/CLI ou conserva HELD.
   Nenhum seed. Remoção/ausência posteriores cobrem start em trânsito.
7. **Reader Linux negativo local:** fonte pública abre pipe local dentro
   do PID1 para matriz pequena de header/trailer/extra/truncado; dados fixos
   e curtos, sem deadlock por capacidade. Usa read_seed_fd real do helper
   verificado. Não enviar frame inválido burlando Seed do host nem criar
   segundo transporte. Emite somente contagens/categorias fechadas e exit0.

Todos usam fonte/casos fixos; ausência de EOF observada só no instante medido
não prova quietude eterna. O script não atribui sucesso de aplicação a SENT.
O caso de não-leitura admite os dois resultados de buffering previamente
declarados; os demais exigem seus oráculos exatos. Falha aborta a rodada,
preserva fatos e recolhe somente recursos próprios; sem retry de caso.

## Supervisão e cleanup

Reutilizar núcleo de ciclo fresco d2b485c2/sampler6bcbdbe5 e journal12 com
replay antes de B, além das primitivas públicas/PS/Docker já revisadas.
Desenho do coordenador concreto ainda será revisado antes de código: nenhum
patch nos helpers congelados para aceitar perfil diferente. Reusar por
herança/composição explícita, com lista exata dos overrides e testes de
invariantes. Preflight confirma Desktop/boot/daemon/contexto/CIDglobalvazio/
imagem exata antes de B; atraso viola janela e aborta sem criar CID.

Cada owner antes do spawn. Foreground cancelado/aguardado antes de quiesce;
quiesce pode ser reavaliado uma vez com outro budget3s se HELD por spawn
tardio, sem recriar start/send. Se continuar incerto, ownership/loop retidos,
sem falso release. Caso e pipeline param; não iniciar próximo canário.
Um watchdog independente de600s acompanha somente CIDs registrados e o
processo CLI próprio com identidade completa; primeiro sinaliza/encerra
foreground, depois confirma coleta, remove próprio CID e registra ausência.
O watchdog não chama close/loop em outro thread. Interação concreta com
event loop travado será fechada no código/revisão, sem prometer cancelamento
de syscall do SO. Nenhum kill por nome parcial ou prune/force.

Remoção normal: quiesce→ticket→inspect por posse/ID→kill se vivo→reinspect→
rm semforce→ausência por CID→Absent(ticket,observed)→close→assert_released.
Se start em trânsito impedir rm, HELD/pêndencia, sem segunda tentativa
implícita. Sem parar Desktop com posse incerta. No final globalvazio antes
de restaurar Desktop próprio off com mesmo boot/PID/FILETIME; se inicialmente
ativo, preservar ativo. Não consumir credenciais nem conectar a outro DB.

## Evidência e gates antes de A

Registrar exclusivamente fontes/hashes/argv públicos/Config/identidade,
categorias/contagens/metadata/estado de pipes, fases reais e cleanup. Os dados
do canário são públicos; ainda assim nenhum mecanismo novo de log de seed
ou do seu hash. Fonte/código, fakes, perfil/estado/raiz/comando únicos passam
por revisão separada antes de executar. Sem nova dependência ou alteração
de produto. A rodada T4 não instala o canal na imagem nem muda o wheel W1.

Após T4 aceita, retomar o fixture PG16 privado do plano NATIVE: shell reader,
tmpfs/socket/UID70/binaries, PKI/segredos em memória e política/matriz próprias
ainda não implementados. Nenhuma credencial atravessa este canal antes disso.

## Precisões W1–W7/O1–O5 antes do código

Direção aceita pelo Claude2. Contrato concreto escolhido sob delegação:

- Watchdog não toca owner/Process/transporte/tarefas asyncio, não cria
  ticket/Absent nem fecha loop. Recebe snapshots imutáveis sob lock antes
  de spawn: CID/nome/task/imagem/comando, e depois PID/FILETIME de criação
  do docker.exe. O main é o único escritor do snapshot. Heartbeat monotônico
  a cada1s, atraso15s ou600s desde B dispara; a janela A mantém os limites
  próprios do núcleo fresco e não é contada como se já fosse B.
- O único sinal para asyncio é callback request_abort previamente fechado
  pelo main, via call_soon_threadsafe. Não inspecionar tarefa em outro thread.
  Se loop parece vivo, pedir cancelamento e aguardar2s por confirmação; se
  não responder, agir externamente. Comparar PID **e FILETIME** antes de
  terminar CLI próprio por comando PS fixo, com handle/creationtime exatos;
  PID reaproveitado recusa. Se spawn ainda não publicou identidade de CLI,
  não adivinhar PID: limpar CID impede start tardio, registrar CLI incerto.
- Depois do CLI identificado, inspect por posse/ID, killCID se vivo,
  reinspect/rm semforce/ausência com subprocessos públicos limitados fora
  do loop. Sem aceitar mera parada ou resposta anterior como release.
  Ações em emergency-NN.json/xb; watchdog disparado implica NOT_PASSED.
- Main continua obrigado a quiesce e **nova** ausência após ticket, mesmo
  se emergência removeu CID antes. Se loop não voltar, HELD/pendência e
  Desktop não restaurado. Thread não-daemon/Event/join limitado35s; se não
  terminar, HELD. Nenhum close/ticket emitido pelo watchdog.
- Fakes cobrem heartbeat parado, PID/FILETIME divergentes, falta de posse,
  nova ausência pós-ticket, recibo alheio recusado e thread não recolhido.

O1: reader Linux é exatamente o helper e6ca9e60, bytes por argv/SHA antes
de compile; medir linha completa≤26000 e import Linux sem efeitos. O2: papelP
UID70 numérico simulado, sem afirmar usuário postgres/PG/Alpine nesta imagem.
O3: no caso1 o canário é comparado **byte a byte** com o público fixo e o
relato contém tamanho/equality=true, sem corpo ou hash do seed. Isso preserva
a regra de não introduzir log de hash do seed; a igualdade exata é o oráculo,
não uma comparação apenas de tamanho. EOF é booleano informativo. Restantes
oráculos3–7 mantêm categorias e inventários exatos definidos acima.

O4: budget por caso, máximo47s: create5 +inspect3 +abertura/envio12 +closeinput3
+observação2 +quiesce/recoleta6 +cleanup15 +fechamento1. Sete casos329s,
mais21s de margem/registro =350s de matriz pós-B. Uma interrupção pode consumir
até18s de coleta/cleanup pendente, restauração do Desktop usa até93s pelos
passos já delimitados e join de watchdog até35s: total496s, abaixo de600.
São orçamentos de supervisão e operações canceláveis, não promessa de syscall
que não retorna. Observações do caso normal/flood usam timeout2s sem ampliar
os deadlines do canal; timeout aborta o lote e segue só cleanup. Demais
casos não ganham repetição ou aumento de cota. Fonte/hash/estado/comando
concretos voltarão à revisão; não executar com base só nesta soma.

O5: inspect/READY/framing/EOF/CLI/handle/tempos serão medições, não premissas.
Uma falha aborta sem ajuste em voo. Antes de código operacional do watchdog,
revisar seu comando PS/PIDFILETIME e a interação exata com o coordenador.

## Calibragem atual antes de A — substitui prazos propostos anteriores

Baseline recovery-rm6,297s confirmado no registro aceito, sem reexecutar.
Teto2s/3s de rm era insuficiente e foi recusado antes de uso T4. Atual:
emergência45s (PS4/absence2/inspect2/kill4/rm8), pins≤1s por chamada após
retorno da leitura, reserva final10s. Pin atual medido0,125s é amostra, não
teto do SO. Sequência mais longa soma24s de comandos +7s de pins +10s de
reserva=41s, margem4s. Watchdog join50s inclui ack2/lock1/executor45/margem2.
Spawn/syscall que não retorna ainda faz join falhar/HELD; não é promessa absoluta.

No main futuro, cleanup normal passa a21s (inspect3+kill4+reinspect3+rm8+
absence3), em vez de15. Caso máximo53s, sete371s, margem29=400s de matriz.
Coleta/cleanup pendente28 +restore93 +join50 =571s totais pós-B, abaixo600.
Substitui47/350/496/30/35 anteriores **somente neste desenho ainda não
executado**; não altera medições, deadlines12/3 do canal ou limites de worker.
Kill4s é orçamento proposto, ainda não medido no T4; falha aborta sem aumento
em voo ou retry. Nenhum novo efeito, quota de memória, rede ou fonte consumida.

## Revisão posterior do binding — contrato atual antes de execução

Precisões e regressões em HOST-DESIGN/VALIDATION. Cleanup22s inclui lock1s;
caso56s inclui relatório4s (1,5s de observação EOF mais margem CLI). Sete
casos392 +22margem =414s matriz;28pendente+93restore+50join =585<600.
Esses números substituem os desenhos acima, nunca medições. T4 não executada.
Flood observa fault sem esperar saída de produtor infinito; retain ausente
reprova o oráculo mesmo quando a limpeza pode comprovar ausência e liberar.
