# B2-C1 — contrato do domínio protegido e reconciliação de orçamento

**2026-10-23 — proposta técnica sob delegação, antes de implementação.**
**Atualização C1:** núcleo implementado localmente em runtime/domain.py,
sem chamador operacional, em fechamento da revisão. O texto abaixo preserva
o contrato revisto antes de código; evidência própria em DOMAIN-VALIDATION.
Próximo incremento depois de HELD III; não uma nova rodada de pressão.
Nenhuma nova D-nnn, backend de SO, API genérica ou liberação de SQL nasce
deste texto. Desenho revisado; D1/D2 e R1/R2 corrigidos antes de código.
Aceite limitado ao núcleo puro, sem chamador operacional. Estado em HANDOFF.

## Problema e direção escolhida

B-2 ainda exige teto individual e agregado do caminho protegido, incluindo
o pai, auxiliares, snapshots/gerações e resultado lento. D-112 contabiliza;
D-113/D-114 limitam o frame e retêm o pin; D-115 codifica já mascarado.
Nenhum desses núcleos impõe cota de SO. HELD III preserva a prova de recusa
do membro, não o teto agregado. Repetir HELD não resolve a lacuna.

Investigar um domínio de dados **separadamente pertencente ao produto**,
opt-in, incluindo supervisor do novo caminho, listener/TLS, trabalhadores
e auxiliares. Não colocar silenciosamente o gateway já aberto, terminal,
Admin ou MCP legado sob um Job Object ou cgroup; nenhum processo existente
é reparentado/migrado. É alternativa de integração, ainda não alteração da
arquitetura operacional aprovada.

Mover o listener para esse domínio exige desenho próprio de snapshot,
controle, leases, shutdown, aliases e fronteiras. O control plane externo
não pode executar SQL ou receber resultados crus; os custos imputáveis
ao caminho protegido **não desaparecem ao mover processos**. Compilação,
candidatos/gerações e snapshots mantidos fora do domínio ainda precisam de
limite e reserva comprovados, ou devem migrar para dentro na proposta.
D-107 legado permanece igual; novo uso relacionado ao caminho protegido
precisa estar incluído/limitado e cobrado. C1 não faz essas migrações.

## Contrato fechado proposto, somente interno

Um registro de evidência por perfil de plataforma/runtime e uma descrição
fechada de custos/ownership; sem plugin/backend extensível ou callback novo.
Dados vêm exclusivamente de colaborador confiável, nunca do cliente SQL,
catálogo editável, frame do worker ou JSON que possa declarar capacidade.

Perfis confiáveis só podem ser constantes frozen de um registro fechado,
em código e revisado. A função confere identidade de membro desse registro,
não apenas igualdade de campos/evidence_ref. String bem formada, clone,
dataclass hipotética e fixture são UNVERIFIED e nunca prontas. O registro
inicial não tem entrada STRICT_PROVEN: inclui somente os perfis históricos
Linux AS128 e Windows Job com suas lacunas; ambos devem resultar NOT_READY.
Não existe setter, registro dinâmico ou carregamento por arquivo/ambiente.
Novo perfil confiável exige código/evidência/revisão próprios, não um ID.

- Kind individual: NONE, AS_VIRTUAL ou JOB_PRIVATE; bytes finitos e exatos,
  capacidade de processos/threads conhecida, momento de associação.
- Kind agregado: NONE, STRICT_PROVEN ou TRANSIENT_DOCUMENTED. Guardar o
  identificador da evidência, escopo, número máximo de membros, limite
  configurado e, separadamente, pico/recusa observados. Um enum não prova SO.
- Vetores distintos: privado mapeado, shared anônimo, tmpfs/file por write,
  page cache, kernel/sockets/pipes, listener/TLS/codec/saída, controlador,
  auxiliares e snapshots/gerações/candidatos. Cada vetor deve ser
  comprovadamente coberto, excluído por construção **com evidência**, ou
  desconhecido. Desconhecido/ausente conflita com prontidão do produto.
  Não somar shmem de novo a file; não chamar VmSize/VmPeak de RAM.
- Topologia antes do spawn: supervisor próprio incluído, máximo de workers
  e auxiliares, criação já no domínio agregado, limites individuais
  conferidos antes do trabalho, inventário/identidade, sem breakaway.
  Import/bootstrap anterior ao AS fica explicitamente separado e cobrado
  no domínio agregado; não declarar AS ativo desde a criação.
- Cleanup físico confirmado por dono confiável; registro de capacidade não
  prova que kill/reap/thread.close ocorreu. Qualquer incerteza conserva
  ownership, créditos e bloqueio de nova admissão.

Não aceitar bool como int, zero/negativo/infinito/NaN, capacidade sem teto,
registro parcial ou campo desconhecido. Identificadores/evidence refs e
coleções têm limites fechados; não carregar documentos arbitrários,
resolver caminhos, calcular SHA ou consultar SO neste núcleo.

## Reconciliação com D-112: não duplicar o ledger

C1 deve **validar** as premissas da reserva; D-112 permanece o único dono
dos créditos. Não criar um segundo ledger, lock ou política concorrente.

Cada custo declara IN_DOMAIN ou OUT_OF_DOMAIN e a grandeza orçada. Total
lógico D-112 continua cobrando todos: M_in + M_out + margem lógica <= M.
Somente M_in pode ser comparado ao limite do domínio correspondente;
M_out precisa de limite independente e evidência confiável para cada custo
imputável fora. Folga de um domínio não cobre falta de prova no outro.
Geração externa sem prova continua NOT_READY, mesmo com M_in cabendo.
Não alegar que um cgroup protege a memória de um compilador externo.

Grandezas permanecem explícitas: VIRTUAL_ADDRESS_SPACE, PRIVATE_COMMIT ou
RESIDENT_AND_CHARGED. Conferir unidades do plano, cotas e limites comparados;
bytes por si não autorizam misturar grandezas. B/P descrevem limite superior
de custo nessa mesma grandeza, não apenas len(buffer). C1 não possui conversão
implícita de AS/private commit em memória física. Se uma prova futura precisar
de conversão conservadora, ela exige novo contrato/evidência/revisão, não
aceitar um float/fator ou nome de unidade fornecido pelo chamador.

O plano declara **uma única grandeza para todo o ledger**: todas as entradas,
dentro e fora do domínio, e a margem lógica precisam estar nessa grandeza.
Entrada IN_DOMAIN em AS e OUT_OF_DOMAIN em resident é NOT_READY, não soma
compatível só porque ambas usam inteiros em bytes.

Para uma cota de worker efetivamente imposta L, a reserva W precisa cobrir
o máximo que ele pode usar: **W >= L**, não W <= L. Reservar W menor que L
permitiria consumo não cobrado. Se L cobre apenas private commit ou AS,
isso não cobre automaticamente os demais vetores; sua classificação deve
continuar bloqueante. Custos fixos/partilhados imputáveis e simultâneos não
podem ser omitidos por já existir outro processo fora do domínio.

B inclui somente custos fixos **sem reserva própria**: supervisor/bootstrap,
listener, estado TLS fixo e auxiliares fixos sem token próprio, cada um com
localização. Geração, candidato e snapshot são cobrados exclusivamente nas
reservas CANDIDATE/GENERATION (shared_bytes) de D-112, nunca também em B.
Auxiliar com token AUXILIARY também não entra em B. Identidade de custo
repetida em dois donos, inclusive BASE e GENERATION, dá NOT_READY por
double-charge; custos distintos que coexistem continuam ambos cobrados.
P inclui buffers/cópias/texto/TLS/output simultâneos por sessão, conforme
D-114. 2F+overhead <= P é cheque lógico mínimo, não limite superior já
calibrado. Descarte em voo mantém o dono original; retirada não mata sessão
admitida para caber no orçamento.

Bases/margens são reservadas antes de alocar, sessões antes do spawn; mesmo
lock do futuro coordenador protege geração/vagas/créditos/shutdown. Créditos
vivos continuam cobrados no idle/envio lento. Falha do núcleo/rollback
mantém HELD. C1 não integra esse lock/registry nem usa bool de fake como
prova de término real.

Topologia é comparada com BudgetLimits, não só com um número declarado pelo
perfil: sessões/workers/auxiliares máximos mais supervisor precisam caber
na capacidade de processos. Capacidade de pids/threads deve incluir todas as
threads declaradas por papel (listener, TLS/I/O/reaper e auxiliares), não
confundir pids.max com número de processos. Bootstrap pré-AS do supervisor
pertence a B dentro do domínio, nunca à cota W de um worker. Ausência de
custo/quantidade/threads de qualquer papel é NOT_READY.

## Semântica de SO: margem não é certificado

[Linux RLIMIT_AS](https://man7.org/linux/man-pages/man2/getrlimit.2.html)
limita espaço virtual individual; um inventário de N processos com limites
L permite argumentar sobre a soma desses espaços, não sobre RAM/kernel
total. Custos de processos extras e bootstrap não podem ser omitidos.

[Cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) documenta
excesso temporário de memory.max. Escolher uma margem sem limite superior
comprovado para esse excesso **não** transforma o domínio em STRICT_PROVEN.
A desigualdade M <= aggregate_bytes - margem é planejamento conservador,
não prova de pico físico. TRANSIENT_DOCUMENTED permanece insuficiente para
o contrato estrito atual até uma alternativa explicitamente justificada,
revisada e medida substituir prospectivamente o contrato correspondente.
Não editar a asserção histórica para fazer FAIL virar PASS.

[Docker](https://docs.docker.com/engine/containers/resource_constraints/)
exige limites explícitos e suporte no kernel. A abstração de limite duro do
CLI não sobrepõe a semântica mais precisa do cgroup. O domínio exclui
VM/containerd/dockerd/host quando essa exclusão for declarada; esses custos
não podem ser incluídos depois por inferência.

Windows Job privado não cobre seções compartilhadas; o agregado histórico
falhou na asserção estrita. Nenhum perfil atual é certificado para SQL.
Linux é candidato de laboratório, não escolha silenciosa do destino.
Sistema operacional/runtime/privilégios/acesso do deploy foram perguntados
ao usuário como informação, sem pedir novamente autorização já delegada.

## Escopo de implementação de C1, condicionado à revisão do desenho

Menor candidato: um perfil frozen, um plano de custos frozen, enum fechado
de motivos e reconcile(profile, plan, BudgetLimits) -> Verdict com ready e
reasons limitados. Apenas dados/transições do D-112 já existentes; nenhuma
máquina de lifecycle nova. Estado hipotético/UNVERIFIED sempre NOT_READY,
e todos os perfis atuais também. A futura ativação deve usar esta função
como precondição única **antes** de criar o ledger; sem esse vínculo futuro
o núcleo é apenas código inerte, não autorização ou gate efetivo.

Validação/reconciliação pura junto do D-112 existente. Sem SO,
threads/processos reais, novo transporte,
ambiente, API pública, conexão, SQL, dependência ou alteração de D-107.
Nenhum chamador operacional nem setting pode habilitar SQL por esse núcleo.
Uma fixture hipotética não vira perfil confiável disponível em produção.

Testes determinísticos contra contrato: tipos/overflow/capacidades,
custo maior/igual/menor que cota, vetores desconhecidos, extra member,
bootstrap fora do limite, margem não comprovada, evidência parcial,
snapshot/auxiliar omitido, output pin vivo, cleanup incerto/HELD e
admissão versus barreira. Não simular a imposição de SO como se fosse
medição; usar os estados reais de D-112 e não duplicar sua máquina.
Se esses cheques exigirem uma segunda máquina equivalente, reduzir o
núcleo à reconciliação e deixar transições no D-112. Contraprovas explícitas:
grandezas diferentes entre IN/OUT e a mesma geração tanto em B quanto em
shared_bytes são NOT_READY, sem alterar estado do ledger existente.

## Caminho finito depois de C1

1. Escolher perfil de domínio de execução com base no destino informado e
   na evidência disponível; mudar contrato agregado, se indispensável,
   somente com justificativa prospectiva e sem dispensar segurança.
2. Backend mínimo com associação desde criação/inventário/kill/reap reais,
   cobertura dos vetores e pai; comando/plano de teste revisados **antes**
   da carga própria. Nenhuma repetição implícita de HELD.
3. Worker interno atrás do mesmo gate: snapshot B-1, conexão upstream única,
   pipeline D-115, frame D-113 e receiver D-114. Fakes para lifecycle primeiro;
   depois equivalência B-1 fim a fim e falhas locais no domínio real.
4. Custo superior medido no produto, concorrência até limite configurado,
   cliente lento, retenção de gerações, OOM/erro nativo, timeout/cleanup e
   zero resultado parcial. Só então avaliar B-2 e D-090 gate2.
5. Apenas após gates próprios: ingresso SQL, compatibilidade certificada,
   MCP multi-datasource, modo operacional e deploy reproduzível.

Este texto não implementa worker nem muda o desenho aprovado da Etapa8.
B-1/B-2/D-090 continuam abertos, PGWire SQL permanece 0A000. Sem outro
escritor, commit/push/deploy, nova carga ou job agendado por este plano.

## Histórico da revisão do desenho

Claude2, somente leitura51ea0d85, confirmou W>=L, diferença entre margem e
prova estrita e preservação dos custos externos. Encontrou D1 (comparação
agregada misturava custos dentro/fora) e D2 (evidence_ref textual não é
perfil confiável); ambos corrigidos antes de código. C-a unidade explícita,
C-b capacidades reais de processos/threads e C-c núcleo mínimo/pré-condição
única também incorporados. Rerevisão fechou D1/D2 e pediu só R1 (uma grandeza
no ledger inteiro) e R2 (dono único de geração/snapshot, fora de B); corrigidos
no texto com contraprovas explícitas antes de código. Parecer condicionou o
aceite a essas duas correções, sem outro bloqueador para núcleo puro pequeno.
Não há implementação C1 ou mudança operacional, nem aval de plataforma.

## Limites explicitados na revisão do código

O trecho anterior "não há implementação" registra o fim da revisão do desenho;
o C1 agora existe, isolado. Nenhum perfil STRICT_PROVEN foi registrado.
O registro Windows preserva SHARED_ANON como GAP_OBSERVED, não UNKNOWN:
é a lacuna medida em B2-B2a, e continua impedindo prontidão.

O perfil Linux histórico tem AS individual e contador residente agregado.
Com uma só grandeza por ledger e sem conversão implícita, esse perfil sempre
produz UNIT_MISMATCH. Uma composição futura das duas grandezas exige novo
contrato/evidência/revisão; não se troca o rótulo para fazê-lo caber.

Identidade de perfil no registro confere a descrição revisada, não atesta
runtime/limites ativos. O plano é dado de colaborador confiável, não prova
física do custo. IDs duplicados são detectados; o mesmo custo físico sob IDs
diferentes depende da correção do plano, sem deduplicação semântica automática.
A integração futura precisa usar no D-112 custos pelo menos tão grandes
quanto os reconciliados, além de provar os limites físicos antes do trabalho.
Este núcleo puro não impõe isso a chamadas posteriores.

Custos são estruturas frozen limitadas a64 entradas, grandeza única, inteiro
exato até2^63-1; zero só significa ausência explícita de auxiliares fixos,
nunca cota ilimitada. Nada é carregado de JSON/catálogo/frame/ambiente.
Transições/pin/HELD continuam no D-112/D-114 existentes, sem segunda máquina.
