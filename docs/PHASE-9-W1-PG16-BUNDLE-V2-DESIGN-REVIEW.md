# Ponte slot A → metadado B — revisão do desenho

Data: 2026-11-06. Decisões sob a delegação vigente, revistas pelo assistente
principal; não são aprovação individual do usuário. Claude2 respondeu apenas
com Read, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo
`claude-opus-5-5`, esforço `medium`. CLI63376/6054/25247/41850 terminaram0,
com terminais recuperados antes da chamada seguinte e sem segundo escritor.

**Estado:** desenho aplicado ao componente privado e teste, revistos com fakes
em [BUNDLE-V2-VALIDATION](PHASE-9-W1-PG16-BUNDLE-V2-VALIDATION.md).
O desenho original foi fechado antes dos testes; as afirmações abaixo sobre
testes futuros descrevem essa ordem histórica. Este lote não cria loader,
entry, coordenador, collector, publicador ou consumidor operacional. As
obrigações desses componentes são premissas explícitas e trabalho posterior.

## Base conferida e mudanças da revisão

Partida HEAD/origin/master `d88823f769220654c81e3a529dadffcad920796f`, árvore
rastreada limpa. O revisor leu o caller A inteiro por trechos, o lifecycle,
runner e backend pertinentes, os contratos de B e a validação anterior.
Conferiu hash e tamanho de 18 fontes/testes: source10, lifecycle/teste,
reconciliação/teste, A/teste e B/teste. Todos intactos; estado16 não editado.
Não executou módulo, fixture ou suíte de testes nesta revisão.

As propostas foram corrigidas para explicitar as origens anteriores aos
efeitos, antecipar contagens, impedir leitura de refs estrangeiros, limitar
escalares antes de encode, guardar todos os slots em torno de cada helper e
separar fatos verificáveis de premissas. Estimativas iniciais de tamanho e o
kind apontado de memória foram substituídos pelos limites abaixo. Nenhum
finding deste lote foi reproduzido por teste: foram observações de desenho.

Referências: [caller A](PHASE-9-W1-PG16-CASE-V2-VALIDATION.md),
[validador B](PHASE-9-W1-PG16-PROVENANCE-V2-VALIDATION.md) e
[contrato de B](PHASE-9-W1-PG16-PROVENANCE-V2-CONTRACT-REVIEW.md).
Os 72/708 de A e 228/1166 de B são medições anteriores, não novas execuções.

## API única e origens

API futura: `bundle(group, slots, measured, nonce)`.
Resultado: `("BUNDLE_READY", evidence)` ou `("BUNDLE_REFUSED", reason)`.
Os pares são tuples exatas com primeiro item str exato. Reason é um dos
13 motivos fechados definidos adiante. Evidence tem a forma aceita pela B:
`(manifest_raw, summary_raw, transport_raw, private_copy, metadata)`.

`group` é tuple exata de oito itens:

`(case_ns, keep, legacy, lifecycle, reconcile, host, registry, private)`.

O produtor futuro captura essas referências **antes de allocate e de qualquer
efeito** e as mantém. Case_ns é o namespace vivo de A; keep é sua lista KEEP;
legacy/lifecycle/reconcile são as fontes de prepare; host é o original;
registry é o _LIVE original; private é o mapa único de artefatos. Uma tuple
entregue no fim só permite comparar identidades. Ela não comprova o momento
da captura nem autentica código; isso depende da cadeia externa confiável.

Perfil deliberadamente estreito: namespace A novo por lote, três casos no
máximo, allocate sob demanda depois de o anterior ser APPROVED e parada no
primeiro REJECTED. Keep contém exatamente os k slots selecionados, em ordem,
sem slots alocados e omitidos. O builder confere seu tipo, tamanho e cada
identidade antes de qualquer varredura; não admite KEEP ilimitado ou seleção
que esconda um slot retido.

| Entrada | Forma |
|---|---|
| slots | tuple exata de 1..3 slots genuínos da mesma classe _Slot vinculada |
| measured | tuple exata `(rows, launcher_sha)`, declarações do loader |
| rows | tuple exata de oito tuples `(role, path, size, sha)`, papéis/caminhos estáticos de B2 |
| Cada linha | str/str/int/str exatos; size 1..65536, nunca bool; sha de 64 hex minúsculos |
| launcher_sha | str exato de 64 hex minúsculos; tamanho do binário fora do schema |
| nonce | str exato de 32 hex minúsculos; origem/frescor garantidos externamente |
| private | dict exato até 11 entradas da whitelist, bytes exatos por arquivo |

Measured não é ExpectedV2: os valores esperados permanecem de posse do
revisor e são fornecidos separadamente à B. Pin medido bem formado mas
divergente pode gerar candidato; a B deve recusá-lo como PIN. Nunca derivar
a política esperada do manifest ou de measured.

## Ligação e preflight limitado

Case_ns: dict exato com até 128 chaves str builtin de 1..64 caracteres,
conferidos nessa ordem antes de lookup/reflexão. _Slot e _Refs têm metaclasse
builtin type; _intact/_released/_record são FunctionType com globais case_ns.
O __init__ escrito à mão de _Slot pode ter seus globais conferidos. _Refs
não possui __init__ próprio: não se inventa vínculo de globais para classes.
Case_ns.KEEP é keep. Legacy/lifecycle/host: dicts exatos até 256 chaves,
com o mesmo limite de nomes, e legacy._LIVE é registry, list exata.

O perfil usa as classes e os descritores originais de _Slot/_Refs/_Context,
clock e Owner como premissa confiável. Não executa descritores arbitrários.
Contexto e identidades originais são conferidos antes de ler atributos do
owner. Nas sondas futuras, controles entram por helpers confiáveis injetados,
não por propriedades maliciosas que o contrato exija executar.

Preflight por slot, antes de callbacks, hash ou encode:

- Classe _Slot exata; state/outcome str exatos READY_FOR_VALIDATION;
  run_reserved True; failure/control None; tree bool exato. Não decidir pelo
  último retorno de run: reentrada pode devolver RETAINED_REUSED sem alterar
  o desfecho primário READY.
- _Refs exato antes de acessar seus campos. Entries é tuple de 34 tuples
  de três itens: mapping por identidade entre legacy/lifecycle/host/case/facts,
  nome str exato de até 64 caracteres e referência original. A contagem34
  vem da captura de A: 10+8+2+2+2+3+1+5+1. Só depois conferir context_type
  contra lifecycle._Context e o tipo genuíno de ctx.
- Meta: tuple de oito itens tipados, conforme A, incluindo número/prefixo,
  nome, diretório já capturado e tuple das 20 chaves. Não reconstruir história.
- Case20/facts10/record13: dicts exatos, contagem antes das chaves builtin,
  depois conjuntos literais e valores. Objeto genuíno mas não inicializado,
  com AttributeError ao ler campo obrigatório, dá SHAPE fechado.
- Slots compartilham os originais do group e o mesmo mapa private. Owner,
  case, facts, retained, ledger, ctx, record, refs, meta e clock são distintos
  por identidade entre slots. Clock é por caso; host é compartilhado.
- Registry exata e vazia **antes de qualquer helper**, evitando uma chamada
  que percorra owners desconhecidos. Ledger original é dict vazio; ctx
  conserva owner/case/fontes/facts/retained/registry/ledger/clock/host originais.
- Lifecycle_reserved True; reconcile_reserved bool igual ao latch tree;
  held None; retained bytearray exato até 1024. Owner.state str exata CLOSED.
  Inconsistência inicial de liberação dá RELEASE; mudança posterior dá DRIFT.

Essas verificações descrevem liberação lógica observada, não quietude do SO.
O builder nunca chama run, lifecycle, finish, close ou reconcile. Tampouco
chama _finished: o snapshot before local do run de A não está no slot, e
reconstruí-lo dos artefatos finais fabricaria uma prova histórica.

## Snapshots e guarda global

Antes de callbacks, capturar grupo e todos os slots com valores escalares
tipados e referências originais. A guarda global roda antes e depois de cada
helper e após construir os bytes, antes de retornar. Revalida formas/tipos
primeiro, depois identidades/valores, em todos os slots, sem chamar helpers
dentro dela. Um helper de slot posterior não pode mudar um anterior sem
detecção nos campos cobertos. Não há congelamento recursivo genérico.

Fingerprint: oito origens; tamanhos/tipos dos namespaces e identidades dos
objetos vinculados; KEEP ordenado; registry vazia; private como pares de
nome/objeto bytes; estado/desfecho/reserva/latches; identidades originais de
cada slot e ctx; meta; flags de metadado do case; snapshot completo do record;
owner CLOSED; ledger original vazio. O alcance do case é essas flags/meta e
as referências de case guardadas por A, não imutabilidade profunda do case.

Precisão registrada na revisão de implementação, sob delegação: tamanho de
namespace significa o tamanho original capturado, não apenas permanecer
abaixo do teto. Os 34 entries precisam continuar apontando aos mesmos valores
nos cinco mapas conhecidos, e os dez campos diretos de `_Refs` conservam
suas identidades. Metadados escalares do case e sua referência de diretório
são capturados antes dos callbacks; a guarda não chama `_meta` novamente.
Não se exige congelar valores de chaves não vinculadas do namespace quando
seu tamanho e a forma permanecem iguais. Classes/descritores e a premissa de
origem continuam os mesmos; isso não autentica alterações anteriores coerentes.

Facts: todos os dez campos, não apenas held e tamanho do buffer. Reason é
None ou enum FACT_REASONS; held é None; terminated/overflow/signaled/eof são
bool exatos; exit_code/total_processes são None ou uint32; turns é uint32.
Retained guarda identidade, tamanho e bytes copiados depois do teto1024.
Isso detecta mudança do conteúdo retido com o mesmo tamanho.

Por slot, no máximo três callbacks, até nove por bundle: _intact, _released,
_record. False exato dá respectivamente DRIFT, RELEASE, RECORD. Retorno não
bool ou Exception comum dá INTERNAL. A pós-guarda precede classificar essa
falha: deriva dá DRIFT. BaseException que não é Exception propaga como o
mesmo objeto, sem uma pós-guarda substituí-lo. Nada escreve nos slots,
owners, listas ou primeiros latches de erro/controle.

São callbacks de leitura confiados à origem, não funções matematicamente
puras: _intact lê clock.now e chama _meta; _released chama o state capturado.
Classes/descritores originais e stdlib sem mutação de entradas são premissas
explícitas. Um namespace inicial malicioso ou alterações coerentes anteriores
ao snapshot não são autenticados por guardas de identidade.

## Escalares e tamanhos antes de serializar

Record tem exatamente os 13 campos do core. Case/outcome/rejection/framing
são enums ASCII exatos; rejection/framing podem ser None. Exit_code e
total_processes são None/uint32, audit_entries e terminate_calls None/int
0..512. Terminated é bool; ready/inner_closed/audit_integral são None/bool.
Seconds é None/float exato finito não negativo, com grafia canônica até32.
Não converter objetos/subclasses nem usar default de json.

Private obedece FILE_CAPS antes de hash: invocation4096, supervision4096,
stdout1024, snapshot4096, audit65536, total até97280. Fora do tamanho, nomes
seguem a whitelist de prefixo; descritores só usam nomes estáticos até32.

Encoding canônico: json com sort_keys, separadores compactos, ASCII e
allow_nan False, mais LF. Dados vêm exclusivamente dos snapshots locais;
dicts de saída são novos, com bytes imutáveis. Não usar mapas vivos durante
encode. O envelope não é profundamente imutável: evidence contém dois dicts.

Limites superiores conservadores, não máximos medidos ou exatos:

| Objeto | Derivação conservadora | Teto escolhido / cap de B |
|---|---|---:|
| Campo genérico | chave ASCII até32 codificada até34 + dois-pontos + valor até66 |101 |
| Record embutido |2 +13×101 +12 =1327 |1536 |
| Summary |2 +9×101 +(8+2+3×1536+2) +9 +LF =5541 |8192 /16384 |
| Descritor |2 +(6+1+34) +(7+1+5) +(8+1+66) +2 =133 |133 |
| Descritor de caso |133 +1 +(8+1+1) =144 |144 |
| Transport |2 +3×101 +(9+1+133) +(9+1+2+11×133+10) +4 +LF =1938 |2048 /4096 |
| Fonte / sources |fonte207;2 +8×207 +7 =1665 |1665 |
| Manifest |2 +2×101 +12 +143 +145 +(7+1+2+3×144+2) +(9+1+1665) +(10+1+77) +7 +LF =2719 |3072 /4096 |
| Metadado |2 +8×21 +(66+1+12+22+4×5) +7 +LF =299 |512 /1024 |

Fonte207 usa role até32, path até64, size até65536 (cinco dígitos) e sha64.
Valores record conhecidos têm até64 caracteres ASCII; uint32 até10 dígitos
e float até32, inferiores ao valor genérico66. Chaves do metadado têm até18
caracteres, codificadas até20; case codificado até12 e slot até22.
Por leitura dos literais de B, MANIFEST_KIND tem41, CASE_KIND37 e maior path50;
o kind do transport39 não é o maior. Todos cabem no domínio conservador.

Manter checagens defensivas dos caps reais após encode. Com esses domínios,
SIZE para os artefatos gerados não tem testemunha isolada alcançável. Testes
devem conferir a aritmética e exemplos de pior domínio, sem alegar cobertura
de um ramo impossível. Os caps de arquivos privados têm negativos alcançáveis.

## Pipeline e metadados

Treze motivos: GROUP, INPUT, CAP, KEEP, SLOT, SHAPE, RECORD, PREFIX,
ARTIFACTS, DRIFT, RELEASE, SIZE, INTERNAL. **Precedência é a execução abaixo,
não a ordem do enum.**

1. GROUP: tuple8, namespace/classes/funções e vínculos iniciais; tipos de
   registry e private, incluindo private≤11 antes de inspecionar suas chaves.
2. INPUT: slots1..3, measured, nonce, nomes/tipos de private.
3. CAP: bytes privados por arquivo e agregado antes de hash.
4. KEEP: lista original, tamanho k e identidades ordenadas.
5. SLOT: classe e flags terminais, sem acessar refs/context_type prematuramente.
6. SHAPE: contagens/domínios de refs/meta/case/facts/record/ctx e origens;
   distinção dos objetos por identidade.
7. RECORD: domínios escalares e snapshot antes de igualdade/prefixo/encode.
8. PREFIX: meta N/nome/prefixo na ordem; anteriores APPROVED, último REJECTED
   ou APPROVED apenas se k=3; nenhum caso após rejeição.
9. ARTIFACTS: conjunto exatamente correspondente aos arquivos de 1..k.
10. RELEASE inicial: registry vazia, ledger original vazio, flags/latch,
    held/retained, ctx original e owner CLOSED, antes de helpers.
11. Captura dos fingerprints limitados; depois, três helpers por slot com
    guarda global, erros/controles conforme a seção anterior.
12. Encode dos snapshots, SIZE defensivo e guarda global final DRIFT.
13. Resultado fechado BUNDLE_READY/evidence ou BUNDLE_REFUSED/reason.

| Campo de case-N/v2-case.json | Origem |
|---|---|
| kind |literal CASE_KIND |
| number / case |meta[1] /meta[0], tipos e prefixo conferidos |
| slot_outcome |desfecho primário READY do slot |
| lifecycle_reserved |flag exatamente True do case |
| reconcile_reserved |flag bool exato do case |
| tree_latched |latch bool do slot, igual ao flag |
| owner_released |True somente após as verificações lógicas frescas; não fornecido pelo chamador |

Tree True implica record REJECTED, com precedência de LAST_CLOSE conservada
por _record e pela B completa. O inverso não é exigido. Summary usa records
copiados e caudas NOT_RUN literais, com pins/scope/admission/kinds congelados;
transport liga summary e privados; manifest liga esses bytes, metadados e
measured pelo schema de B2. Constantes duplicadas terão provas futuras contra
runner/core/B. O builder não verifica a si mesmo: verify_v2 continua obrigatório.

## Matriz futura e obrigações externas

Próximo incremento: somente testes do builder, com harness A real sobre
fakes e B/core reais, primeiro revisão/RED, depois módulo. Nenhum teste novo
foi escrito ou executado nesta revisão. Cobrir os cinco cenários já aceitos,
prefixos1/2/3, reentrada sem apagar READY, determinismo e isolamento de cópias;
grupos trocados, KEEP extra, slots/owners compartilhados; contagens antes de
scanner/helpers e refs falsos sem acesso de atributos; domínios/caps antes
de encode; registry não vazia sem varredura/callback; drift de slot anterior,
inclusive facts e retained de mesmo tamanho; retornos não bool/Exception,
deriva concorrente à falha e controle por identidade; measured divergente
com candidato aceito apenas na forma e PIN recusado pela B.

Inventário textual de namespaces (sem exec): caller57 nomes/maior19,
runner58/16, lifecycle33/14, host85/17. Uma margem de nove globais dá
66/67/42/94, abaixo de128/256 e64. Isso não é contagem em execução: sanidades
positivas futuras continuam necessárias.

BUNDLE_READY só fornece candidato. Não permite sair, publicar, liberar posse
ou repetir efeitos. Repetir um build de dados estáveis pode ser determinístico;
isso não é retry operacional. Recusa não limpa nada; o produtor continua
retendo referências e seu controlador futuro decide o estacionamento.

Coordenador deve garantir captura anterior e perfil serial; loader deve
conferir/executar os mesmos bytes; produtor/publicador deve montar e validar
tudo antes de um commit terminal, sem _publish antigo seguido de arquivos
extras. Falha pós-efeito ou resultado desconhecido não dá retry/release/exit.
Collector V2 e protocolo de publicação têm revisão própria. Esses componentes
continuam inexistentes. Não há assinatura, prova de frescor, execução real,
quietude do SO ou autenticação contra Python privilegiado.

Source10/estado16/fontes aceitas permanecem fixos. Attempt3f12dc584c29 segue
consumido FAILED_ONLY_OPERATOR_ABORT; identidade Nov2 não foi promovida.
Nenhum novo Native/Docker/PG/SQL, leitura privada/runtime/config/binário,
root/nonce/entrada/loader/collector/publicador/CLI/comando operacional ou
deploy. Nenhum job/quota/conta/modelo trocado. Gateway indisponível e
Native3s/entry_gate/B1/B2/D090gate2/C1/SQL/produção abertos. O destino aceito
continua OracleLinux9.8 em Docker local.
