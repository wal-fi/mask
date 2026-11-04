# Entrada privada da coleta — retenção em primeiro plano (desenho, testes antes)

Estado final revisto,2026-11-04: fonte3d309771/26337bytes e testes2e18c2b5/
38239bytes;120próprios e868relacionados aprovados com fakes. Evidências,
falhas históricas e limites em
[validação](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-ENTRY-VALIDATION.md).
Os registros V2–V7 abaixo preservam o estado de cada rodada, não representam
pendência atual dos gates simulados nem ativação nativa.

Data: 2026-11-04. Sob a delegação geral vigente (trabalho rotineiro autônomo,
com proibições explícitas e permissões efetivas valendo) e revisão do root;
não é aprovação individual. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Nesta etapa existem só este desenho e
`tests/test_pg16_shell_native_control_collect_entry.py`; o módulo
`docs/poc/pg16_shell_native_control_collect_entry.py` não existia nas etapas
de testes (histórico abaixo); foi implementado na V5 (seção 8), pendente da
leitura e dos gates do root. Nenhum teste executado pelo programador.

Histórico: o primeiro teste (`f850633b`, 27130 bytes) deu, medido pelo root,
81 coletados, 79 erros + 2 falhas, todos `FileNotFoundError`, 3,258 s; a
contagem preliminar de 82 do programador estava errada. Ruff 0, mypy 0,
format 1 (a assinatura de `test_a_malformed_source_capture_refuses` cabia em
uma linha). V3 corrige esse formato, mantém os 81 casos e acrescenta 10
casos previstos (seção 7); total a medir pelo root.

V3 medido pelo root (`182ad729`, 31841 bytes): 91 coletados, 89 erros + 2
falhas, todos `FileNotFoundError`, 0,977 s; AST confirmou as 81 definições
originais inalteradas; Ruff e mypy limpos; format reprovou só a assinatura de
`test_a_failing_keep_never_replaces_the_first_control` (cabe em uma linha).
O root também reproduziu um erro de preparação do teste: `_open` é campo de
instância, ausente do `__dict__` da classe, e o `monkeypatch.setattr` da
injeção de atributo ilegível levantaria `AttributeError` antes de `decide`.
V4 junta a assinatura e passa `raising=False` nessa única chamada, para criar
de propósito a `property` na classe; é a preparação correta da injeção, não
supressão do comportamento esperado. Nenhuma asserção ou caso mudou.

Lido de fonte real nesta chamada e na anterior: composição `37b098cf`
inteira, entrada `356d` inteira. De leituras anteriores da sessão: coletor
`1972ec74` (`_ACTIVE`/`_POISON` são listas de módulo) e construtor do
backend `ccb3f74a` (`_open` dict, `_retained` list, alterados só no lugar).

Fixos: composição `37b098cf…`, coletor `1972ec74…`, backend `ccb3f74a…`,
verificador `b375`, entrada `356d`, orquestrador `b419`, adaptador `eaeb`,
backend de controle `10c9`, chamador `dfcc`, testes 63/29 e estado16. Sonda de
identidade consumida em 2026-11-02, rótulo LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED
inalterado. Destino final Docker Oracle Linux 9.8; gates de produção abertos.

## 1. Arquivo e superfície

Um arquivo, mesmo padrão da entrada `356d` (S0–S6, `KEEP`, `_STATE`
pegajoso, `decide`/`settle`/`cycle`/`_hold`/`_drive`), sem framework, proxy
dinâmico, cópia de fonte, monkeypatch ou limpeza. `_LIVE` da entrada não cobre
a coleta e não é usado. Único `__main__`: `raise SystemExit(main(sys.argv[1:]))`.
`REPO = Path(__file__).parents[2]` léxico; nada lido ou resolvido no import.

Constantes: `SOURCES` (três tuplas caminho/SHA/tamanho: composição 5373,
coletor 20571, backend 22315), `KIND = MASKGW_PG16_NATIVE_COLLECT_ENTRY_V1`,
`EXIT_OUTCOMES = {0: VERIFIED_APPROVED, 1: VERIFIED_REJECTED, 2: REFUSED,
5: INTERRUPTED}`, `PARK_REASONS = (RETAINED, UNKNOWN_CUSTODY, INTERRUPTED,
INTERNAL)`.

Seams (globais do módulo; trocados só por testes): `_read_sources()`
(leitura limitada, `lstat` regular sem reparse, apenas os três fontes Python
públicos; `Path.resolve` só aqui), `_argv0()` (em S1, deriva
`str(<repo resolvido>/.venv/Scripts/python.exe)`, a mesma forma de
`host["PYTHON"]` do orquestrador; nunca `sys.executable`, argv atual nem
leitura do `.exe`), `_execute`, `_install`, `_pids`, `_pause` e
`_native_api(ns)`, que no lote futuro devolveria `ns["_load_native"]()`.
`_native_api` real **não é criada nem chamada agora**; nos testes é sempre
fake. Chamá-la de verdade é ativação nativa e exige revisão própria.

## 2. Estágios

- **S0** um argumento: nonce de 32 hex minúsculos ⇒ senão `FINAL 2
  COLLECT_ENTRY_ARGV`.
- **S1** `_read_sources()` devolve tupla de 3; cada item `bytes` exato,
  tamanho e SHA do pin, todos antes de qualquer `compile`/`exec`; depois
  `_argv0()` `str` exato, não vazio, ≤1024, sem NUL ⇒ senão `FINAL 2
  COLLECT_ENTRY_SOURCE`. S0/S1 são as únicas recusas puras (sem `KEEP`).
- **S2 LOAD** `_progress` pré-alocado em `KEEP`; namespace `N` em `KEEP` antes
  do `exec` dos bytes da composição; captura imediata do `_ATTEMPTS` original
  (`list` exata, vazia) e de `_collect_pinned` chamável; senão
  `COLLECT_ENTRY_LOAD`.
- **S3 ARM** par de PIDs validado (`int` exatos, `0 < v < 2**32`,
  distintos), depois `SIGINT`/`SIGBREAK`, depois `IDENTITY`; senão
  `COLLECT_ENTRY_ARM`.
- **S4 ATTEMPT** `attempted = True`, `active = True`, uma chamada
  `N["_collect_pinned"](coletor, backend, None, nonce, argv0,
  api_factory=<fábrica>)`. O desfecho vai direto ao progresso pré-alocado
  (`outcome` e, se controle, `control`) antes de qualquer registro falível;
  segunda falha não substitui a primeira (`_fault`).
- **S5/S6** `decide` puro, `settle` pegajoso, `_drive` protegido, `_hold`.

## 3. Fases de custódia (sem capturar o que ainda não existe)

| Fase | Prova |
|---|---|
| antes da tentativa | só o corpo puro da composição executou; sem efeito possível |
| tentativa, fábrica não entrada | `_ATTEMPTS` original capturado vazio antes; o código pinado não chama api antes da fábrica; resultado fechado ou controle podem sair |
| fábrica entrada | trava `factory_entered` antes de inspecionar; captura exata de `record` (único em `_ATTEMPTS`, `record.native is ns`), `record.collector`, `_ACTIVE`, `_POISON`; depois `record_captured`; só então `native_started` e `_native_api(ns)`; captura incompleta ⇒ PARK |
| depois de `native_started` | sem backend capturado ⇒ PARK conservador (retorno `None` ou exceção não provam ausência de efeito) |
| primeira operação | adaptador fixo `_Observed(progress, api)` com exatamente as 7 operações: trava `op_entered`, captura `record.backend`, `_open`, `_retained` exatos e só então delega; `_retained` pode já conter a chamada pendente e não é copiado nem normalizado; sem backend ⇒ `OSError` sem delegar. A busca `getattr` do construtor não delega nem captura. |

Predicado de quiescência (`_trusted`), sob `try`, por identidade e tipo
exato. Carga falha antes de o registro existir: confiável **só** se `N`
continua `dict` exato com apenas as chaves reservadas iniciais e seus
valores (falha pura antes de inicializar o registro); qualquer chave extra,
`_ATTEMPTS` não vazio, subclasse ou valor malformado ⇒ PARK
`UNKNOWN_CUSTODY`, sem adotar um vazio posterior. "Antes de
`attempted = True`" sozinho não prova saída segura. Carga saudável: `N`
`dict`, `N["_ATTEMPTS"] is attempts` (`list` exata), vazia até a tentativa,
mesmo antes de S4. Fábrica não entrada: `len(attempts) <= 1`. Fábrica
entrada: `record_captured`, `attempts == [record]` com `attempts[0] is
record`, `record.collector is collector`, `_ACTIVE`/`_POISON` originais
`list` exatas vazias; com `native_started`, backend capturado, `record.backend
is backend`, `_open` `dict` exato vazio, `_retained` `list` exata vazia.
Contêiner trocado por vazio posterior, subclasse ou inspeção que falha ⇒
falso. Referência registrada não é limpeza.

## 4. Decisão e saída

EXIT só com `_trusted` e não estacionado; forma `("EXIT", code, reason,
summary, transport)`:

- não tentado ⇒ `2` com `COLLECT_ENTRY_LOAD`/`ARM`/`INTERNAL`;
- controle ou não chamado ⇒ `5 INTERRUPTED`;
- retorno: tupla exata de 4 com `str` exatos; `VERIFIED_*` + `"OK"` + dois hex
  minúsculos de 64 ⇒ `0`/`1`; `INVALID` + motivo não `OK` do `REASONS`
  (`frozenset` exato) do coletor original capturado, ou, sem coletor
  capturado, da lista local fechada (`COLLECT_SOURCE`, `COLLECT_UNAVAILABLE`,
  `COLLECT_POISONED`, `COLLECT_ARGUMENT`, `COLLECT_INTERNAL`) ⇒ `2`; qualquer
  outra forma ⇒ `2 COLLECT_ENTRY_RESULT` (nunca 0/1).

PARK: ledgers originais intactos mas não vazios ⇒ `RETAINED`; identidade,
captura ou inspeção incerta ⇒ `UNKNOWN_CUSTODY`; demais ⇒ `INTERNAL`.
Estacionar marca `parked` antes de emitir `PARKED` uma vez; nada o desfaz;
saída quebrada, EOF, retorno inesperado ou controle repetido não liberam nem
repetem. Handler: `KeyboardInterrupt` só com `active`.

Eventos JSON canônicos ASCII, `kind` próprio: `IDENTITY` (`nonce12`,
`controller_pid`, `parent_pid`), `FINAL` (`nonce12`, `controller_pid`,
`code`, `outcome`, `reason`, `summary_sha256`, `transport_sha256`; hashes só
em 0/1), `PARKED` (`nonce12`, `controller_pid`, `reason`). Sem caminho, raw,
`argv0` ou texto de exceção. `FINAL` escrito antes do `return` não prova saída;
uma rechecagem falha depois dele estaciona. Saída terminal do tool e
artefatos continuam necessários.

## 5. Testes (antes do módulo; 81 casos na V2 medidos pelo root, mais os da seção 7)

Pureza do import (sem resolve, leitura ou sinal), pins e constantes, AST
(imports, `_load_native` só em `_native_api`, `resolve` só nos helpers
preguiçosos, `_hold` sem `return`/`break`, um `return` em `_drive`, travas
só com `True`, uma chamada de `_native_api`, um `__main__`); `main` só nas
recusas S0/S1 (argumentos, adulteração das 3 fontes, captura malformada,
`argv0` malformado) sem `_drive`/`_execute`; passagem única pela composição
real com fakes: aprovado/rejeitado com identidade de todos os originais e
saída fechada, nenhuma operação antes da captura, `INVALID` fechado, passagem
única; adaptador sem delegação no construtor e sem backend; fechamento
incerto, controle na coleta (primeiro controle mantido), controle antes da
fábrica ⇒ 5, lacunas da api nativa (controle, erro, `None`) ⇒ PARK,
`_ATTEMPTS` trocado antes da chamada, 10 trocas/tipos hostis depois; recusas
de carga e de identidade; resultado malformado nunca 0/1; `settle`
pegajoso; sentinela fora da saída; saída quebrada; handler; `cycle`. O
`main`/`_drive`/`_hold` reais nunca rodam nos testes.

## 7. Refinamento V3 (contrato fixado pelos testes novos)

Limitação documentada da composição `37b098cf` (não é achado nela): uma
falha comum dentro da fábrica vira `COLLECT_INTERNAL` com o registro retido,
mas a exceção e o traceback são descartados pela composição; um objeto local
só alcançável pelo traceback seria coletado. O chamador retém:

- `progress["fault"]`: a **primeira** falha comum ou exceção privada;
- `progress["control"]`: a **primeira** `BaseException` que não é
  `Exception`, independentemente.

A fábrica e as 7 operações do `_Observed` capturam toda `BaseException`,
gravam-na diretamente no progresso pré-alocado **antes** de qualquer
`KEEP.append` falível, e relançam o objeto original. Tracebacks originais
nunca são limpos (é a prova de retenção). `_fault` nunca levanta e não
substitui o primeiro valor. Nenhum texto de exceção é publicado.

Auxiliares com nome fixo, chamados por nome global:

- `_capture_record(progress, native_ns)`: captura `record`, `record.collector`,
  `_ACTIVE`, `_POISON` e só no fim marca `record_captured`; a fábrica marca
  `factory_entered` antes de chamá-lo;
- `_capture_backend(progress)`: captura `record.backend`, `_open`,
  `_retained` e só no fim marca `backend_captured`; a operação marca
  `op_entered` antes de chamá-lo e só delega depois dele.

Casos novos: falha privada com `Token` local só por `weakref`, viva após GC
via `progress["fault"]` e seu traceback, com PARK `UNKNOWN_CUSTODY` e
sentinela fora da saída; `KEEP.append` falhando com `OSError` ou segundo
controle depois do primeiro controle do helper nativo (primeiro mantido, sem
escapar); controle dentro de cada auxiliar de captura (trava verdadeira,
captura falsa, nada delegado, PARK); carga parcial (`_ATTEMPTS` não vazio,
subclasse, tupla, chave inesperada) ⇒ PARK antes da tentativa; atributo
original do backend ilegível depois de uma passagem boa ⇒ PARK. O caso
`test_a_load_failure_is_a_closed_refusal` (namespace intocado) continua EXIT 2.

`_native_api` real segue só prospectiva, nunca chamada nos testes; nenhum
teste roda `main` positivo, `_drive` ou `_hold` reais.

## 8. Implementação (V5)

Testes congelados `c868fef7` (31927 bytes, 91 casos; RED medido pelo root:
91 `FileNotFoundError`, 1,005 s; Ruff/format/mypy do teste limpos; única
mudança semântica desde `182ad729` foi a injeção deliberada com
`raising=False`). Escrito só `docs/poc/pg16_shell_native_control_collect_entry.py`
e esta seção, sob a delegação geral e revisão do root, sem aprovação
individual. O programador não executou testes; hash, resultado e gates ficam
para o root. Nenhuma captura, carga, chamada nativa, instalação de sinal ou
invocação real; o código só define a entrada futura.

Estrutura: `main` (S0 argumento, S1 `_read_sources` + `_pinned_sources` das
três fontes antes de qualquer `exec`, depois `_argv0`); `_drive` protegido
(único `return`), `_advance` em uma passagem com travas (`loaded`, `armed`,
`_STATE["attempted"]`), `_register` do `_ATTEMPTS` original após carga
saudável, `_arm`, `_invoke`; `_factory` com `_capture_record` antes de
`native_started` e `_native_api`; `_Observed` com as 7 operações explícitas
e `_capture_backend` antes de delegar; `_fault` grava `fault` (primeira
`Exception`) ou `control` (primeira outra `BaseException`) no progresso
pré-alocado antes do `KEEP.append` protegido, sem tocar tracebacks; fábrica
e operações relançam o objeto original. `_inspect`/`_custody` devolvem
`QUIESCENT`, `RETAINED` ou `UNKNOWN` pelas fases da seção 3, com a regra de
carga pura da seção 7 (namespace com só a chave reservada `__name__`).
`decide`, `settle`, `_park`, `_announce` (uma linha, saída quebrada engolida),
`cycle` e `_hold` seguem a entrada `356d`. `_verdict` exige tupla exata,
`str` exatos e par legal; `REASONS` do coletor capturado (`frozenset`
exato) ou `COMPOSITION_REASONS` locais antes dele.

Limites desta implementação: `_native_api` e `_read_sources`/`_argv0` reais
nunca foram exercitados; `_capture_failed` levanta `OSError` com texto fixo,
nunca publicado; um `return None` da fábrica não prova ausência de efeito e
estaciona. Uma regressão que estacione um caminho positivo de `main` em teste
pode travar o processo; os testes evitam isso por construção.

## 9. Revisão da candidata V5 — regressões antes da correção (V6)

Candidata `da8992b9` (22966 bytes, 678 linhas), congelada nesta etapa. O
root leu o código inteiro e mediu os 91 testes: 90 aprovados, 1 falha,
11,039 s; Ruff, lint do PoC, format e mypy limpos. A falha é do **harness**:
`test_broken_output_changes_no_decision` usava `patch.setattr("sys.stdout",
...)` dentro de `sealed`, e o pytest atual resolve o alvo em texto chamando
`importlib.import_module`, que está proibido. V6 importa `sys` no teste e
passa o objeto (`patch.setattr(sys, "stdout", Broken())`); as asserções não
mudaram.

Três achados privados de contrato reproduzidos pelo root (não exploração
externa medida), agora com regressões no fim do teste, a medir em RED antes
de qualquer correção da fonte:

- **F1 controle na inspeção.** Uma `BaseException` levantada ao ler um
  original (`_open` como `property` que levanta um `Signal` uma vez e depois
  devolve o original) escapa de `settle`/`decide`; o `_fault` do driver e um
  segundo `settle` permitiriam EXIT 0 com `parked` falso. Exigido:
  inspeção totalmente fechada a `BaseException`; o primeiro controle gravado
  no progresso antes de qualquer registro falível; PARK pegajoso, mantido
  mesmo quando a leitura volta a funcionar (latch próprio, que não muda o
  EXIT 5 legítimo de um controle anterior à fábrica).
- **F2 decisões de saída forjadas ou velhas.** `settle` aceitava qualquer
  quíntupla de forma (por exemplo `("EXIT", 0, "NOT_OK", "not-a-sha",
  "not-a-sha")`). Exigido: normalização completa com tipos exatos e pares
  legais código/motivo/hashes, e igualdade com a decisão recomputada do
  desfecho **atual** validado; qualquer outra (subclasse de `str`, código
  `bool`, motivo ou hash errados em qualquer lado, código 2 com motivo
  desconhecido, sentinela ou hash, código 5 com motivo ou hash errados, ou
  decisão válida mas incompatível com o desfecho atual) estaciona sem
  publicar sucesso nem segredo. Não é autenticação de chamador público.
- **F3 guarda de identidade antes de cada delegação.** Com o `_ACTIVE`
  original trocado por um vazio depois da primeira delegação, a candidata
  ainda fez 343 delegações ao fake (31 criados, 31 fechados) e só então
  estacionou. Exigido: um único guarda estrutural, reaplicado antes de toda
  delegação, que confere identidade e tipo exato de toda a cadeia (namespace
  da composição e `_ATTEMPTS`, registro, `record.native` capturado
  explicitamente, `record.collector`, `_ACTIVE`, `_POISON`, backend,
  `_open`, `_retained`) e **não** vazio (durante as operações as listas
  originais normalmente não estão vazias; vazio só no `settle`). Cadeia
  desconhecida ⇒ recusa imediata, sem delegar, inclusive fechamento; nada
  de fechamento forçado ou repetido; estado original e backend retidos;
  decisão PARK `UNKNOWN_CUSTODY`. Também um `record.native` trocado por cópia
  depois de uma passagem boa estaciona (não adotar cópia posterior).

Direção mínima da correção (não aplicada): um latch pegajoso de inspeção
incerta em `_custody`/`settle` com `except BaseException` gravando o
primeiro controle; `settle` revalidando a decisão por igualdade exata com a
decisão recomputada e por forma normalizada; captura de `native_ns` na
fábrica e um `_guard(progress)` único usado pelo `_Observed` antes de cada
delegação e reaproveitado por `_inspect`.

Distinção mantida: a definição preguiçosa `_native_api` **existe** na fonte
desde a V5, mas **nunca foi invocada** (nem por testes, que sempre a
substituem). Não é "código de fábrica ausente"; é código prospectivo não
chamado, cuja chamada real é ativação nativa com revisão própria.

## 10. Correção dos invariantes (V7)

RED medido pelo root com a candidata `da8992b9` intacta e os testes
`e9c25833` (38207 bytes): 120 coletados, 92 aprovados, 28 falhas, 0 erros,
14,286 s (26 `AssertionError`, 2 `Signal` escapando); os 91 antigos passaram
depois do alvo direto `sys`. Ruff e format limpos; o mypy apontou só duas
variáveis locais `fired` sem anotação nos dois testes F1. V7 muda no teste
apenas essas duas linhas (`first = Signal()` e `fired: list[bool] = []`),
sem tocar asserções, casos, decoradores ou auxiliares; 120 casos.

Correções na fonte (programador sem execução de testes; verde não alegado):

- **F1**: `_custody`, `decide` e `_accepted` capturam toda `BaseException`;
  `_fault` grava diretamente o primeiro controle ou falha antes do registro
  falível; o latch pegajoso `inspection_unknown` é marcado antes de
  devolver PARK/UNKNOWN e, depois disso, `_inspect` devolve sempre UNKNOWN,
  mesmo que a leitura volte a funcionar. O latch só nasce de inspeção
  incerta ou do guarda; um controle comum anterior à fábrica continua dando
  EXIT 5.
- **F2**: `_exit_shape` normaliza a forma completa (`str` exato `EXIT`,
  código `int` exato, `OK` + dois hex de 64 para 0/1, motivo não `OK` e
  hashes `None` para 2, `INTERRUPTED` e hashes `None` para 5); `_accepted`
  exige igualdade, elemento a elemento com tipo exato, com a decisão
  recomputada agora por `decide`; `settle` e o `return` de `_drive` usam
  `_accepted`. Decisão velha ou forjada estaciona. Não é autenticação de
  chamador.
- **F3**: `native_ns` original gravado na fábrica antes de inspecionar e
  antes do helper nativo; `_chain` confere identidade e tipo exato de
  namespace, `_ATTEMPTS`, registro, `record.native`, `record.collector`,
  `_ACTIVE`, `_POISON`, backend, `_open`, `_retained`, sem exigir vazio;
  `_guard` (único) roda no `_Observed` antes de **cada** delegação, depois
  da captura na primeira; cadeia desconhecida marca o latch e recusa com
  `OSError` antes de delegar, inclusive `close`; `_inspect` reaproveita
  `_chain` e só no fim olha o vazio.

`_native_api` continua definida e **nunca invocada**. Limites: o latch é por
progresso; sinais entre duas instruções de `_fault`/`_custody` não são
blindados; nada disso é limpeza nativa.

## 6. Lacunas

Ativação e verificação nativas (a definição preguiçosa existe, nunca foi
invocada); conversões do `_NativeApi`, ABI do CPython alvo, perfil
da âncora, suporte das classes e `NtClose` reais; procedimento exato,
permissões efetivas e comando revisados antes de qualquer captura, carga ou
invocação real; janelas de console/término externo herdadas da entrada.
Native3s NOT_MEASURED, entry_gate NOT_EVALUATED.
