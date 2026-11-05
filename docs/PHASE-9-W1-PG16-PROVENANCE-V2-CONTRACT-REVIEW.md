# Proveniência V2 — revisão do contrato, sem implementação

Data: 2026-11-05. Decisões de desenho tomadas sob a delegação vigente,
revistas pelo assistente principal; não são aprovação individual do usuário.
O Claude2 respondeu somente com Read, na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Terminais CLI64019, CLI81666, CLI27053 e CLI93433 recuperados com exit 0.
Não houve chamada simultânea nem edição pelo Claude2 neste lote.

**Estado:** contrato prospectivo fechado para orientar o próximo RED. O
módulo e o teste de proveniência V2 ainda não existem. Esta revisão refina
e substitui as formas, a API, a ordem e a matriz preliminares de B3/B4/B6
em [CASE-V2-DESIGN](PHASE-9-W1-PG16-CASE-V2-DESIGN.md). Os schemas dos
artefatos, os oito papéis/caminhos de B2 e a separação operacional de B5
permanecem. Nenhum código congelado foi alterado.

## Retomada e evidências desta revisão

Partida HEAD/origin/master `c293175364a57574162911bb82b73ce27101d4d2`,
rastreados limpos. A tarefa `Maskgw-Claude2-Resume-01a05804` executou às
23:05 UTC / 20h05 de São Paulo, com LastTaskResult 0; esta conversa recebeu
a mensagem. Após o término, NextRunTime está vazio: não há próxima ocorrência.
Nenhum novo job foi criado. As leituras retornaram sem API429 após o horário
anteriormente informado; isso não mede o instante exato de reset da quota.
Zero escritor confirmado antes das chamadas e após o último terminal.

O revisor leu B e a validação de A, todo o core congelado por trechos e o
seam `_verify` do collector. Conferiu hash e tamanho de 16 arquivos: source10,
lifecycle e teste, helper e teste, caller e teste. Todos iguais às referências
aceitas. Estado16 não foi editado. Nenhuma suíte foi executada nesta revisão.
Os 72 próprios/708 relacionados de A continuam resultados anteriores,
sem nova medição ou alteração de seus bytes.

Inventário **estático de texto** do core: 86 nomes únicos declarados no topo,
maior nome com 18 caracteres; mais uma margem de nove nomes padrão de
loader/runpy dá 95, abaixo dos limites 128/64 escolhidos. O core não foi
executado para contar seu namespace. Os futuros positivos com o core real
continuam obrigatórios.

## API e entradas exatas

Única função prevista: `verify_v2(core, expected_v2, expected_core, evidence)`.
O módulo futuro é `docs/poc/pg16_shell_native_control_provenance_v2.py`.
Importação apenas define; nenhum carregamento de fonte, exec, leitura,
processo, impressão ou integração operacional pertence ao validador.

| Entrada | Forma |
|---|---|
| `core` | dict real de globais do core congelado, já carregado por uma cadeia externa confiável; não uma cópia do dict retornado por runpy |
| `expected_v2` | tuple exata de dois itens `(rows, launcher_sha256)` |
| `rows` | tuple exata de oito tuples exatas `(role, path, size, sha256)`, na ordem estática de B2 |
| Cada linha | tipos exatos str/str/int/str; papel/caminho iguais aos literais; `1 <= size <= 65536`, nunca bool; sha de 64 caracteres hex minúsculos |
| `expected_core` | instância exata da classe Expected do namespace vinculado |
| `evidence` | tuple exata de cinco itens `(manifest_raw, summary_raw, transport_raw, private, metadata)` |
| Raws | bytes exatos, sem subclasses ou conversão |
| `private` | dict exato, até 11 entradas nos nomes literais do core; valores bytes exatos |
| `metadata` | dict exato, até três entradas `case-N/v2-case.json`, N de 1 a 3; valores bytes exatos |

Rows e launcher são política de posse do revisor, nunca derivados do
manifest não confiável. O tamanho do launcher continua fora do schema.

Os pins de host, adapter, backend e launcher dessa política devem coincidir
com os quatro PINS congelados do core; o pin de core_verify deve coincidir
com `b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10`.
Os valores completos de PINS estão no core e em B2; o validador terá literais
próprios, conferidos pelos testes futuros. Política esperada incoerente dá
EXPECTED mesmo se o manifest a repetir; divergência do manifest em relação
a uma política coerente dá PIN. Isso impede duas declarações desconectadas
de serem aceitas separadamente pelo envelope e pelo core.

## Ligação, snapshots e limite da confiança

O namespace deve ser dict exato com até 128 chaves; cada chave é str builtin
de 1 a 64 caracteres, conferida por iteração antes de lookup/cópia/reflexão.
`verify`, `_verify`, `_capture` e `_parse` devem ser FunctionType com
`__globals__ is core`. Expected e _Invalid têm metaclasse builtin type.
_Invalid tem MRO por identidade (_Invalid, Exception, BaseException, object),
`__init__` escrito à mão com os mesmos globais e sem ganchos extras.
O conjunto permitido de seus atributos próprios é `__module__`, `__init__`,
`__doc__`, `__dict__`, `__weakref__`, `__firstlineno__`, `__static_attributes__`.
Os dois últimos são opcionais em versões mais novas; compatibilidade de
execução fora do ambiente medido ainda exige prova própria.

Não se infere autenticidade pelos globais do __init__ gerado do dataclass.
O construtor e o descritor __dict__ do Expected são premissas do carregador
confiável. Original e clone usam a mesma guarda de campos: dict exato com
duas entradas, chaves str builtin antes de qualquer acesso, campos nonce e
argv0. Nonce: str exata de 32 hex minúsculos. Argv0: str exata de 1 a 1024
caracteres sem NUL. Ambos capturados uma vez, antes de qualquer callback.
Somente um Expected **novo**, com as mesmas duas strings por identidade,
será passado ao verify completo; nunca o objeto original.

Mapas de **dados externos** — namespace, campos do Expected, private,
metadata e objetos JSON parseados — exigem tipo/contagem e chaves builtin
antes de qualquer acesso/comparação. Coleções aninhadas também exigem seus
tipos e comprimentos previstos antes de comparar seus valores.

Os mapas de **política confiável** são outra coisa: LITERALS, LINES, KINDS,
PREFIX_FILES e FILE_CAPS recebem somente guarda de tipo dict e identidade.
Seu conteúdo não é iterado, lido ou congelado pelo envelope. Em particular,
PREFIX_FILES mantém suas chaves inteiras legítimas 1/2/3. WHITELIST e REASONS
são frozenset exatos; LIMITS, tuple exata. PINS é tuple de quatro tuples de
dois str exatos, comparados aos literais somente depois de checar os tipos.
São nove referências de política, incluindo PINS, além das seis referências
de funções/classes. O mappingproxy de atributos de _Invalid não é um mapa
de dados externos nem passa por um congelador recursivo.

A guarda reconfere namespace limitado e identidades/tipos antes e depois
de cada parser, construtor ou verify, antes de consumir retornos. Após uma
exceção comum a pós-guarda tem precedência: deriva dá CORE_BINDING. Controles
BaseException que não são Exception propagam imediatamente como o mesmo
objeto, sem uma pós-guarda substituir o controle original.

Identidade não detecta conteúdo de política alterado no próprio lugar nem
um namespace malicioso desde o início com formas/globais compatíveis.
Isso é uma limitação da política escolhida, não impossibilidade fundamental
de detecção. Namespace novo, privado e estável e execução dos bytes pinados
são premissas externas. A verificação de formas não autentica código Python.

## Limites preservados

| Item | Bytes |
|---|---:|
| Summary / transport | 16384 / 4096 |
| Invocation / supervision / stdout / snapshot / audit | 4096 / 4096 / 1024 / 4096 / 65536 |
| Interno: summary + transport + private | 262144 |
| Manifest / cada metadado, até três | 4096 / 1024 |
| Externo combinado | 269312 |

O wrapper antecipa o teto de 11 entradas correspondente à whitelist válida;
MAX_PRIVATE 64 do core permanece intacto. Com todos os limites individuais
e os 11 nomes permitidos, private soma no máximo 97280, interno 117760 e
externo 124928. As checagens agregadas permanecem como defesa, mas não há
testemunha isolada que as exceda preservando os limites anteriores. Não
se planeja nem se declara cobertura de um teste impossível de isolamento.

## Ordem efetiva de recusa

O conjunto fechado tem 12 motivos: CORE_BINDING, EXPECTED, INPUT, CAP,
SCHEMA, NONCE, PIN, BINDING, PREFIX, METADATA, CORE_INVALID, INTERNAL.
**A sequência abaixo, e não a ordem desse conjunto, define precedência.**

1. CORE_BINDING: formas limitadas e ligação inicial.
2. EXPECTED: forma/pins coerentes de expected_v2 e snapshot dos dois campos.
3. INPUT: formas/nomes/contagens e snapshots de evidence e dos dois mapas.
4. CAP: limites de bytes antes de parser/hash/callback.
5. SCHEMA: parse canônico do manifest e seus schemas exatos de B2.
6. NONCE: nonce do manifest igual ao capturado.
7. PIN: oito fontes e launcher iguais à política coerente esperada.
8. BINDING: nome/tamanho/sha somente de summary e transport.
9. PREFIX: prefixos privados exatamente 1, 1/2 ou 1/2/3; k igual a executed;
   cobertura exata de metadata; lista cases com k descritores em ordem,
   number int exato e name literal. Nenhum lookup de metadata antes disso.
10. BINDING: tamanho/sha dos metadados cuja presença já foi comprovada.
11. METADATA: parse/schema de cada metadado. Number/case corretos, slot
    READY_FOR_VALIDATION, lifecycle_reserved/owner_released exatamente true;
    reconcile_reserved/tree_latched bool exatos e iguais.
12. Construção e guarda do Expected novo; falha própria dá INTERNAL.
13. Verify completo congelado, **uma única vez**, sobre o clone e snapshots,
    sem arquivos V2 em private. Resultado exato tuple de dois str antes de
    qualquer igualdade. APPROVED/OK e REJECTED/OK aceitos; INVALID com motivo
    nos 16 CORE_REASONS dá CORE_INVALID; qualquer outro par/forma dá INTERNAL.
14. Parse do summary já validado; anomalia dá INTERNAL. Todos APPROVED dão
    prefixo 3; senão, primeiro REJECTED define o prefixo, que deve ser k.
    Tree latched true exige record REJECTED, senão METADATA. O inverso não
    é exigido; um caso pode ser rejeitado sem reconciliação.
15. Par V2_VERIFIED_APPROVED/OK ou V2_VERIFIED_REJECTED/OK. Toda recusa usa
    V2_INVALID/motivo fechado, sem caminho, texto de erro ou objeto estranho.

O parse é o _parse congelado: ASCII/canônico, LF único final, profundidade32,
sem duplicatas/NaN/Infinity, domínios numéricos de B2. _Invalid do parser vira
SCHEMA no manifest, METADATA nos metadados e INTERNAL no summary pós-core.
Outra Exception de callback vira INTERNAL, ressalvada a precedência da
pós-guarda. Construtor/verify levantando qualquer Exception dão INTERNAL.
Retornos com forma/subclasses/chaves estrangeiras recebem o motivo exato
da fase antes de chamar igualdade; controles preservam identidade.

## Matriz futura e findings de desenho resolvidos

R1–R12 corrigiram coerência de pins, clone dos dois campos, bounds do
namespace, alcance das guardas, caps redundantes, saídas exatas, mudanças
deliberadas de API/motivos, prefixos, ordem presença/hash, prioridades e a
distinção entre mapas externos e PREFIX_FILES. Foram findings de leitura;
não se afirma reprodução por testes nem RED neste lote.

Os testes futuros devem usar o core real e fixtures sintéticas independentes,
com um namespace falso explícito apenas para contadores/deriva/controles.
Precisam cobrir positivos APPROVED e REJECTED nos prefixos 1/2/3; full verify
uma vez com clone; cada pin; schema/canonicalidade; tipos exatos e chaves
hostis; limites alcançáveis; deriva e controles em cada callback; tipos de
retorno e razões desconhecidas; constantes iguais ao core; e prioridades:

| Combinação | Resultado esperado |
|---|---|
| Metadado ausente, descritor válido | PREFIX, sem lookup |
| Ausente e sha de metadado errado | PREFIX |
| Sha do summary errado e metadado ausente | BINDING |
| Metadado presente com sha errado | BINDING |
| Parse manifest / metadado / summary pós-core com forma inválida | SCHEMA / METADATA / INTERNAL |
| Deriva simultânea a _Invalid | CORE_BINDING |
| Controle simultâneo a deriva | mesmo controle, sem substituição |
| Arquivo V2 em private | INPUT, não CORE_INVALID como no rascunho antigo |
| Razão desconhecida devolvida pelo core | INTERNAL |

Primeiro escrever/revisar testes e medir sua ausência de funcionalidade;
só depois congelar o RED e autorizar um incremento de implementação.
Nesta retomada o acesso foi somente Read. Não se iniciou esse próximo lote.

## Obrigações externas ainda abertas

Loader deve conferir e executar os mesmos bytes capturados em namespace
privado; coordenador/publicador deve derivar metadados dos slots e montar
todos os bytes antes de um único commit terminal; collector V2 precisa de
revisão própria. Validador, loader, coordenador, collector e publicador têm
pins externos acíclicos, sem auto-hash. Os oito papéis selecionados não são
o fechamento completo do código executado.

Envelope válido não comprova origem, frescor, execução real, SO, identidade
viva ou cleanup. Origem/frescor e vínculo ao lote pertencem à cadeia externa
futura. Evidência v1 não pode ser promovida a V2: attempt3f12dc584c29 continua
consumido FAILED_ONLY_OPERATOR_ABORT; identidade Nov2 não reclassificada.
Nenhum consumidor operacional existe neste lote, nem houve Native/Docker/
PG/SQL, leitura privada/runtime/config/binário, root/nonce/entrada/loader/
CLI/comando operacional ou deploy. Gateway indisponível; Native3s
NOT_MEASURED, entry_gate NOT_EVALUATED, B1/B2/D090gate2/C1/SQL/produção abertos.
