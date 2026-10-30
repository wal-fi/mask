# Docker local — decisão prospectiva sobre o contrato de recursos

**2026-10-23 — Opção A aprovada explicitamente pelo usuário; implementação
e evidência ainda pendentes.** Resposta literal: "A", depois da apresentação
do contrato e de suas duas alternativas. Nenhum critério está comprovado
por essa resposta, e SQL continua bloqueada até gates/evidências passarem.
Destino informado: família RHEL/Oracle Linux9 em Docker nesta máquina
Windows. O usuário confirmou Oracle Linux9 disponível9.8 pela pergunta
assíncrona em2026-10-23. Nenhuma imagem foi baixada ou executada.

## Por que a decisão não pode ser substituída por mais testes

O contrato B-2/D-116 atual exige domínio agregado STRICT_PROVEN, sem pico
acima da cota em todos os vetores. A documentação do kernel/cgroup v2 diz que memory.max
pode ser excedido temporariamente. RLIMIT_AS limita espaço virtual do
processo, sem cobrir cache/kernel/sockets/tmpfs por write. Não existe prova
atual para converter uma grandeza na outra, nem margem que por si dê essa
garantia. O perfil Windows também tem lacuna compartilhada já medida.

Fontes técnicas primárias:
- https://docs.kernel.org/admin-guide/cgroup-v2.html (Memory Interface Files,
  memory.max; excesso temporário e OOM)
- https://man7.org/linux/man-pages/man2/getrlimit.2.html (RLIMIT_AS)
- https://docs.docker.com/engine/containers/resource_constraints/

Claude2, sessão51ea0d85, revisão somente leitura do destino/contrato:
sem bloqueador para W1 interno isolado, mas **o contrato B-2 estrito não é
comprovável com os mecanismos disponíveis neste Docker**. Pediu decisão
prospectiva explícita antes de qualquer extensão C1/ativação. Este parecer
não é autoridade para alterar requisito aprovado. Delegação de escolhas
técnicas não será usada para esconder essa troca de garantia de recursos.

## Opção A proposta — perfil Docker com falha fechada sob pressão

Aplicável só ao novo perfil de **teste local** Docker Desktop/WSL2 nesta
máquina. Não se estende a produção em outro host/kernel, RHEL/Oracle bare
metal ou outros containers. Atualização de kernel/runtime/Desktop exige
revalidar evidência e compatibilidade, não aproveitar silenciosamente o
perfil anterior. Não reclassifica experimentos ou perfis atuais NOT_READY.

1. Todo o caminho de aplicação novo fica dentro do container: controlador,
   compilação/candidatos/gerações, listener/TLS/saída, workers e auxiliares.
   Não migrar processo Windows/MCP/Admin/terminal existente. Nenhum Docker
   socket montado. Windows/Docker Desktop/VM/daemon e clientes externos
   ficam fora desse domínio, explicitamente; não há promessa de teto de
   RAM total da máquina ou isolamento contra outros containers do usuário.
2. Limites Docker de memória/swap/pids finitos e nofile finito **por processo**,
   impostos desde criação; agregado de descritores no máximo pids×nofile,
   além do cap de sessões. Conferir limites reais, incluindo memory.swap.max=0;
   sem swap adicional e limites AS herdados por worker antes de trabalho.
   Sem --privileged/cap-extra, alterar kernel/WSL/Windows ou limites até dar
   verde. Workers podem elevar o próprio oom_score_adj para preferir serem
   vítimas; isso não garante que o pai ou outro worker inocente sobreviva,
   nem vira critério de prova. memory.max precisa caber na memória disponível
   da VM; OOM global da VM está fora deste domínio e continua uma limitação
   do teste local, não garantia de isolamento do host Windows.
3. A garantia agregada passa a ser a **semântica documentada de memory.max**,
   com reclaim/OOM e possibilidade de excesso temporário, **não pico<=cota**.
   Nenhuma tolerância numérica não comprovada é inventada. Reservas lógicas,
   admissão antes do spawn, limites de input/resultado e buffers orçados
   continuam obrigatórios. AS e memória cobrada terão reconciliação separada
   de duas grandezas; não somar nem reetiquetar bytes como equivalentes.
4. OOM/falha nativa/prazo/integridade incerta encerra a sessão ou o container;
   nunca retorna valor bruto/parcial, reconecta, reenvia SQL ou libera vaga
   antes de confirmar término/descarte. Parent pode ser vítima de OOM;
   ou um worker inocente pode ser vítima; uma sessão pode derrubar outra ou
   causar indisponibilidade de todas. Controlador PID1 (ou único filho de
   init mínimo que encerra junto), workers com EOF/PDEATHSIG e corrida de
   parent verificada, de modo que morte do namespace termine descendentes.
   Provar essa limpeza; preferência de OOM não a comprova. Reap/HELD são
   garantias **locais**: backend upstream pode continuar SELECT até perceber
   desconexão ou statement_timeout/timeout do servidor; reap local não prova
   término imediato da query no PostgreSQL.
   Perfil inicial com restart explicitamente **no**. Reinício manual só a partir
   de estado persistente validado e recursos anteriores encerrados; sem
   replay de operações ou consultas. Se outra política for proposta depois,
   terá evidência própria antes de usar.
   D-114 permanece: morte durante envio pode deixar um prefixo de frame
   **já validado e mascarado** no socket; completude então é não comprovada,
   conexão fecha e não há retry. Não prometer envio TCP atômico ou resposta
   completa após morte do pai; o que nunca sai é linha/frame sem proteção.
5. Vetores precisam de controle/evidência: rootfs read-only, tmpfs/shm com
   limites explícitos e sem uso arbitrário pelo worker, sockets/FD/processos
   limitados, cache/kernel contabilizados pelo domínio e verificados.
   Admin precisa escrever catálogo/config: não prometer zero writes
   ou zero cache do container inteiro. Volumes próprios, entradas/sizes e
   retenção gerenciada limitados; seus custos entram no perfil. Volume Docker
   local não tem cota de disco por padrão: aplicação confere tamanho/retenção,
   com escrita atômica existente (temporário/replace) e startup fail-closed
   em par parcial/incoerente após OOM, sem reparar silenciosamente corrupção.
   Não considerar shm-size como teto para MAP_SHARED anônimo.
   Kernel accounting precisa ser efetivo (sem cgroup.memory=nokmem; campos
   memory.stat conferidos); ausência é bloqueante. Páginas tmpfs/shm por
   write podem ser cobradas no domínio sem aparecer no AS: não excluí-las.
6. Aceite novo, a demonstrar **depois** da decisão: limites efetivos dentro
   e fora conferidos; baseline/capacidade/concurrência e reservas coerentes;
   pressão privada/compartilhada, file/cache/kernel representativos, cliente
   lento e gerações coexistentes; falhas de worker/pai e cleanup/restart
   manual medidos; zero resultado bruto/parcial e nenhuma execução no pai.
   Cada lacuna não coberta permanece bloqueante ou exigirá decisão de risco
   específica, nunca uma marca DOMAIN_PROVEN colocada só por este texto.
7. Sigilo entre processos: workers e controlador que manipulam credenciais
   precisam de dumpable=0 antes de ler segredos, confirmado e testado contra
   ptrace/proc de outro processo com mesmo UID, sem CAP_SYS_PTRACE.
   Execve normal reinicia dumpable: aplicar no processo final antes de
   receber material secreto, sem confiar em flag do launcher anterior.
   Workers sem segredo em argv/env, ambiente explícito por allowlist e
   entrega só no canal fechado depois de confirmar essa proteção. No
   controlador, secrets de mount/arquivo validado ou ambiente sanitizado
   antes de qualquer filho; nunca herdar o env padrão nos workers. Limpar
   env não é prova de apagar bytes da RAM ou de /proc; dumpable e ordem
   de criação continuam necessários.
   Core0 mais dumpable=0, core_pattern e fs.suid_dumpable efetivos registrados
   (pipe pode ignorar RLIMIT_CORE). Combinação suid_dumpable=2 e pipe é lacuna
   bloqueante até prova específica de que a proteção funciona nesse perfil;
   não se afirma que o valor2 sozinho contorne um PR_SET_DUMPABLE=0 efetivo.
   Não trocar kernel/core_pattern/suid_dumpable do host. Conferir swap0
   efetivo para os processos; não alegar que isso controla swap do Windows.
   Logs do runtime serão none ou explicitamente limitados em tamanho/rotação,
   somente metadata fechada, sem stdout/stderr de dados/DSN/segredos. Log do
   daemon/administrador Windows fora do domínio não vira segredo protegido
   por este perfil. Esses controles são requisitos, ainda não implementados.
   Preservar THREAT-MODEL: código/processo/secret provider do Gateway são
   confiáveis; isso não é promessa de preservar masking após comprometimento
   arbitrário do próprio worker, que conhece os dados originais. Os controles
   acima reduzem exposição/coredump/acesso entre processos; não criam uma
   nova garantia contra RCE nem substituem confiança no produtor do frame.
8. Contratos de masking, read-only, sigilo, snapshots, uma conexão/sessão,
   confirmação de escrita administrativa e não abandonar recursos ficam
   intactos. B-1 fim a fim e D-090 precisam de evidências próprias. Aprovar
   esta opção **substitui prospectivamente só para este perfil** o aceite
   estrito de B-2 pelos itens3–7. **B-2 só fecha depois que a evidência do
   item6 e os controles do item7 passarem.** A classificação C1 terá nome
   próprio diferente de STRICT_PROVEN e a reconciliação de duas grandezas
   exige revisão/implementação/evidência próprias. Aprovação desta proposta
   não cria perfil confiável pronto, não aprova SQL nem declara B-2 fechado.

**Troca explícita de disponibilidade/recursos:** aceita-se que a memória
cobrada possa ultrapassar temporariamente a configuração e que o processo
principal/container ou o worker de outra sessão possa morrer sob pressão,
interrompendo também sessões inocentes e exigindo reinício manual.
Não se promete preservar todas as sessões ou proteger toda RAM do Windows.
Dados devem continuar protegidos e falhas fechadas; se isso não for provado,
o produto não será liberado mesmo com aceitação da opção.

Fontes adicionais dos controles propostos:
- https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html
- https://man7.org/linux/man-pages/man5/core.5.html
- https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html

## Opção B — manter literalmente a garantia estrita aprovada

B-2 continua bloqueado neste destino até existir mecanismo e prova que
cumpram pico agregado<=cota em todos os vetores. Não se anuncia que Docker
comum oferece essa garantia nem se dá prazo fictício para resolvê-la.
Worker/protocolo/testes internos podem avançar, SQL operacional continua0A000.
Propor outra plataforma/mecanismo depois exige nova análise; não instalar
VM ou alterar o computador por inferência.

## Trabalho independente que continua autorizado

W1: worker persistente de teste e framing fechado, snapshot D-111, corpo
D-118, prazo imposto pelo pai, D-112/D-114 ownership/pin e falha fatal
persistente. Sem hook de limite no Windows, medir como **não protegido**,
somente fixtures/SQL interna em PG16 descartável e procedimento próprio
revisado. Nenhum consumidor operacional ou bypass de C1. Rodar sob domínio
Linux real e certificar recursos fica pendente. Antes de implementar W1,
seu protocolo, segredo/framing/deadlines/cleanup terão desenho revisto.

Estado atual: Opção A escolhida explicitamente; aceite novo prospectivo
aplica-se só ao perfil de teste local. Não altera FAIL históricos nem marca
perfil C1 pronto. Ainda sem mudança em runtime/domain.py, limites físicos,
dependência/configuração nova, carga/worker real ou SQL. Receita inicial
de runtime em deploy/ ainda não executada. Preparação de imagem/procedimentos
sob a delegação vigente pode seguir, sem declarar deploy ou disponibilidade.
