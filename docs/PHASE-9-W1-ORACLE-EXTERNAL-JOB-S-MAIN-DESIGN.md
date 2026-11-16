# W1: main Windows de S e park de retenção — desenho prospectivo SM3

2026-11-16. Somente desenho, sob EXTERNAL-JOB-S-MAIN-REVIEW SM-R2 e SM-R1 (normativas), EXTERNAL-JOB-MAIN-BINDING-REVIEW MB4 (normativa), MB3, MB2 e MB1, com XJ3/EJ1–EJ6 e XE2/ER1–ER3. Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, claude-opus-5-5/medium. SM3 substitui SM2 (`28f023cc`) e SM1 (`700f42ed`), que o root preserva. A correção de SM3 se limita ao guard de custódia em §5 e aos oráculos de §9.3 e §9.8.

Decisões registradas sob a delegação vigente. Isto não é aprovação individual nem admissão nativa.

**O que este documento não é:** fonte, teste, oráculo, perfil alocado, argv, caminho real de executável, payload de ambiente, comando, invocação ou valor operacional. Não autoriza nenhum efeito. O fonte e o teste próprios continuam AUSENTES.

**O que fica fixo:** entrada `b4826e0b` e teste `1835ba81`; N-S `465ae906` e teste `37a757ad`; backend `10c9058f`; adaptador `eaebedd6`; qualificador `999f4a8d`; C0 `43ffbf92`/`c695a68b`; todos os testes, pins, app124, state16 e a tentativa consumida. O main Linux `deploy/oracle9_w1_main.py` é outro processo e fica preservado.

## 1. Arquivos e fronteira

- **Arquivos futuros:**
  - fonte único: `docs/poc/oracle9_w1_external_job_s_main.py`;
  - teste único: `tests/test_oracle9_w1_external_job_s_main.py`.
- **Uso da entrada pinada:** só `load_adoption`, `EntryCustody`, `run_entry` e `MAX_TURNS`, todos do namespace carregado em §3.
- **Proibido:**
  - qualificador ou C0 em runtime (nem import, nem leitura);
  - Owner, wrapper de Owner, launcher, fábrica genérica;
  - ledger privado e monkeypatch.
- **Pureza do import:**
  - O corpo de módulo contém só imports, definições e constantes inertes, sujeitos aos classificadores congelados de `1835` (`import_violations`/`import_effects`) sem alteração.
  - O guard final é exatamente `if __name__ == "__main__": raise SystemExit(main(sys.argv[1:]))`.
  - Esse guard é a única ENTRADA da invocação, não uma dispensa de pureza do restante.

## 2. Entradas abstratas, portas e holder

**`argv`**
- `list` exata com dois `str` exatos: aplicação e diretório.
- Domínio de cada caminho, idêntico ao do qualificador `999f`:
  - padrão de caminho local de `qual:53`;
  - comprimento 1..`_PATH_LIMIT` (`qual:46`);
  - o mesmo `fullmatch` (`qual:281-286`).
- A linha composta (§4) respeita `_COMMAND_LIMIT` (`qual:47`).
- O padrão fica no main como constante INERTE `str`, `_LOCAL_PATTERN`. A chamada de regex (`re.fullmatch(_LOCAL_PATTERN, value)`) acontece só dentro de `_inputs`. Não há objeto compilado no módulo.

**Portas**
- `sys.stdin.buffer` e `sys.stdout.buffer`, capturadas uma vez por `main` e guardadas no holder.
- O main só as repassa a `run_entry`; nunca lê, escreve, faz flush nem fecha.
- stderr nunca é referenciado.

**`SHolder`**
- `@dataclass(slots=True, repr=False)`, com `__repr__` redigido.
- Exatamente estes 10 campos, sem outro estado e sem registro global:

| Campo | Tipo | Default | Escrito |
|---|---|---|---|
| `reader` | `Any` | `None` | captura de stdin binário |
| `writer` | `Any` | `None` | captura de stdout binário |
| `entry` | `types.ModuleType \| None` | `None` | §3 |
| `adoption` | `Any` | `None` | `entry.load_adoption()` |
| `request` | `Any` | `None` | §4 |
| `custody` | `Any` | `None` | `entry.EntryCustody()` fresca (§4) |
| `entered` | `bool` | `False` | `True` imediatamente antes da única chamada de `run_entry` (§5) |
| `result` | `object` | `None` | retorno exato de `run_entry` |
| `first_error` | `Exception \| None` | `None` | primeira `Exception` observada pelo MAIN |
| `first_control` | `BaseException \| None` | `None` | primeiro controle observado pelo MAIN (§6) |

- `main` cria um holder vazio, único por processo, e o retém até o fim de S, inclusive no park.
- Os slots guardam REFERÊNCIAS. Isso não prova vida física de handles.

## 3. Carregamento da entrada pelos mesmos bytes

**Leitura**
- Irmão fixo: `oracle9_w1_external_job_entry.py`, SHA-256 completo `b4826e0b649e37b485b4ca065e225e1103cbd41e19836c2ac95ca78172a62e18`, 16.809 bytes.
- Exige arquivo regular, sem reparse point final, limite de 65.536 bytes, uma leitura limitada e tamanho do `lstat` igual aos bytes capturados.

**Execução**
- Os MESMOS bytes são compilados com `dont_inherit=True` e executados num `ModuleType` novo, de nome privado fixo, com `__file__` igual ao caminho real. Assim `load_adoption` acha o N-S irmão (`entry:154`).

**Registro temporário em `sys.modules`**
- Necessário porque a entrada define dataclasses com annotations adiadas. Segue o padrão do loader C0 (`setup_probe:104-123`).
- Se o nome já estiver presente, a carga é recusada antes do `exec`.
- O módulo é registrado só durante o `exec`. No `finally`, o binding é removido apenas se ainda for o próprio. O de outro nunca é alterado.
- Não há cache, registro persistente nem loader genérico.

**Depois:** `holder.adoption = entry.load_adoption()`, uma vez.

**Falhas**
- Falha comum: recusa de fase A (§6).
- Controle: park.

## 4. Request, custódia fresca e orçamento

**Request**
- Construído a partir de `holder.adoption.Request` e só dele.
- `application` e `directory` vêm de argv.
- `command_line` e `environment` são o perfil NATURAL já revisto em `999f`:
  - ambiente `_ENV` (`qual:52`);
  - código `_NATURAL_CODE` (`qual:56`);
  - composição de `qual:291`, no ramo NATURAL qualificado por `qual:580`/`qual:589`.
- O main declara constantes próprias e uma função de composição própria (`_natural_command(application)`), IGUAIS por comparação estática (§9.4). Este desenho não reproduz os literais.
- Construir o Request é puro. A validação real acontece no `setup` (`backend:337-359`), e uma recusa ali sai como `SETUP_REFUSED` da entrada.

**Custódia:** `holder.custody = entry.EntryCustody()`, criada por `_prepare` e nunca substituída nem reutilizada.

**Orçamento**
- Decisão: o MESMO `entry.MAX_TURNS` pinado, conferido estaticamente contra `MAX_TURNS` do qualificador (`qual:44`).
- É teto de turnos de decisão. Não é timeout de parede, configuração de operador nem garantia de término.

## 5. Chamada única e mapeamento

**`_enter(holder) -> int | None`**
- Todo o corpo fica numa ÚNICA região `try … except Exception … except BaseException`, contendo:
  1. **Guard de reentrada:** se `holder.entered is not False`, devolve `None` (park) sem chamar nada e sem efeito novo.
  2. **Guard de custódia:** exige, só por campos públicos do carrier exato:
     - `type(holder.custody) is holder.entry.EntryCustody`;
     - `holder.custody.claimed is False`;
     - `holder.custody.owner is None`;
     - `holder.custody.first_control is None`.

     Se qualquer condição falhar, ou a forma for opaca, devolve `None` (park). Não marca `entered`, não chama SDK, não faz lookup de portas e não altera custódia nem referências: uma custódia usada pode reter um Owner vivo.
     - Não clona o `_empty` inteiro da entrada, não lê ledger e não edita a entrada.
     - O fluxo normal passa porque `_prepare` cria a própria custódia fresca.
  3. `holder.entered = True`.
  4. A única chamada `holder.result = entry.run_entry(adoption, request, reader, writer, entry.MAX_TURNS, custody)`.
  5. A classificação e o mapeamento abaixo.
- `_enter` tem um único local de chamada, em `_run_s`, executado uma vez.
- Não há laço, retry nem segundo caminho até `run_entry`.

**Mapeamento** (decisão; todos os valores são int32 dentro de XJ3):

| Resultado (`str` exato) | Saída do processo |
|---|---|
| `DONE` | 0 |
| `DONE_NONZERO` | 10 |
| `REFUSED` | 11 |
| `SETUP_REFUSED` | 12 |
| `ACK_FAILED` | 13 |
| `REJECTED` | 14 |
| `RETAIN` | park (`None`) |
| qualquer outro valor ou tipo | park (`None`) |

- Só DONE usa 0.
- PASS em H continua exigindo a conjunção própria da XJ3 com `s_code` 0. Nenhum código sozinho prova liberação.
- Não há protocolo de stdout além do ack da entrada.
- REJECTED quer dizer que a entrada não criou um Owner NOVO nem escreveu (`entry:407-412`). Não quer dizer que não existe Owner anterior.
- A saída 14 só é liberação porque o guard de custódia (passo 2) já garantiu custódia própria sem claim, sem Owner e sem controle. A saída depende dessa precondição, não do rótulo isolado.
- O contrato não cobre adversário capaz de alterar código ou globais confiados.

**Recusas de fase A, antes de `entered`:**

| Causa | Saída |
|---|---|
| argv fora do domínio | 2 |
| `Exception` comum em carga, `load_adoption`, Request ou custódia | 3 |

## 6. Regiões, erros e controles

**`_run_s(argv, holder) -> int | None`**
- **Região A**, só `try` em volta de `_inputs`, `_load_entry` e `_prepare`:
  - `Exception` → `first_error`, saída 2 ou 3;
  - controle → registro e `None`.
- `_enter(holder)` é chamado DEPOIS e FORA da região A. Uma falha depois de `entered=True` nunca vira 2/3.

**Região C, dentro de `_enter` (§5):**
- `Exception` → `first_error` → `None`;
- controle → regra abaixo → `None`;
- inclui falhas da própria classificação e do mapeamento.

**Região externa, em `main`:** envolve a captura das portas e `_run_s`.
- `Exception` com `holder.entered is False` → 3.
- `Exception` com `entered` True, ou qualquer controle → park.
- Esse caminho só é alcançável por resíduo, porque A e C capturam tudo.

**Registro**
- `holder.first_error` só se vazio.
- `holder.first_control` só se vazio E `holder.custody is None or holder.custody.first_control is None`.
- O main nunca escreve na custódia e nunca substitui o controle retido pela entrada.
- Handlers só com atribuições puras: sem re-raise, sem atribuição de traceback/contexto, sem `bool`/`str`/`repr`, sem SDK, sem IO.

**Fase A não é livre de recurso**
- C pode já estar em S, duplicado por H depois do Start de S (XJ3 §6), e não há `CloseHandle` explícito de C.
- Para H isso é ack `MISSING` com erro `ACK_MISSING`.
- Não existe P criado por S nessa fase (`entry:389-393`).

**Resíduo declarado** (sem alegação de contenção ou de B4 global):
- controles entre bytecodes fora das regiões (entre regiões, no `return`, no `raise SystemExit` do guard, no encerramento do interpretador);
- exceções ignoradas pelo interpretador ao finalizar os streams.

## 7. Silêncio

- O único escritor de stdout é o ack da entrada (`entry:256-266`).
- O main nunca escreve em stdout ou stderr.
- Tudo dentro das regiões é retido, então não há traceback.
- `SystemExit(int)` não imprime nada.

## 8. Park

**Forma**
- `_park_s(holder) -> NoReturn`.
- Laço externo infinito; `try` em volta de um laço interno de espera; `except BaseException: continue`.
- `holder` permanece referenciado.

**O que o park nunca faz**
- `return`, `raise`, `break`, close, terminate, escrita, registro de controles posteriores ou substituição do primeiro.

**Fatia**
- Decisão: o MESMO valor fixo de `_PARK_SLICE_S` do C0 pinado (`setup_probe:44`), declarado como constante própria e conferido estaticamente.
- Sem import do C0 em runtime.
- A fatia não é prazo, contenção nem prova de quitação.
- A única chamada é a espera da stdlib, como em `setup_probe:320-328`. Sem thread, sinal ou loop de produto.

**Quem estaciona**
- `main` chama `_park_s(holder)` quando `_run_s` devolve `None` ou quando a região externa (§6) decide park. Nesse caminho `main` não retorna.
- Os testes nunca executam o park real nem esperas reais.

## 9. Costura de teste e oráculos (antes da fonte)

**Funções específicas do fonte:** `_inputs`, `_load_entry`, `_prepare`, `_enter`, `_run_s`, `_park_s`, `main`. Sem camada genérica de decisão: o mapeamento é a tabela de §5, dentro de `_enter`.

**Costura, sobre a MESMA `AdoptionLoad`:**
1. Holder vazio.
2. `_load_entry(holder)` real, sobre os bytes pinados reais.
3. `_prepare(holder, fictional_application, fictional_directory)` real, uma única vez. É puro, sem SDK.
4. Instalar só os seams já aceitos na cópia privada do backend dessa mesma carga: `holder.adoption.backend["_load_api"]` e `["sys"]`, como no teste `1835`.
5. Pôr no holder as portas falsas `Reader`/`Writer`.
6. Chamar `_enter(holder)` uma vez.

**Regras da costura**
- O `EntryKernel`, `Reader` e `Writer` vêm de `1835` por import, sem edição.
- `_prepare` nunca é chamado de novo depois dos seams, porque outra carga criaria outro backend.
- Proibido: fake Owner, fake entrada, patch de produto vivo, `main`/`_run_s` com argv válido, park real.

**Oráculos, nesta ordem:**
1. **Sanidades do fake:** reuso das helpers congeladas e dos pins.
2. **Pureza e forma:**
   - classificadores congelados aplicados ao corpo menos o guard;
   - forma exata do guard;
   - sem import de qualificador, C0, `tests`, `ctypes`, `subprocess`, threads, sockets ou `runpy`;
   - nenhuma regex compilada no módulo;
   - `stderr`/`print` nunca referenciados; `stdin`/`stdout` só em `main`.
3. **Estrutura:**
   - um único local de chamada de `run_entry` e de `_enter`;
   - guard de reentrada, guard de custódia (as quatro condições exatas de §5), marcação de `entered`, chamada, classificação e mapeamento dentro do MESMO `try` de `_enter`, nessa ordem;
   - `_enter` fora da região A;
   - nenhum laço ou retry até `run_entry`;
   - handlers só com atribuições;
   - nenhuma escrita na custódia;
   - AST do park conforme §8;
   - região externa consulta `entered`.
4. **Compatibilidade estática** (o teste lê `999f` e `43ffbf92` por SHA e faz parse, sem executar):
   - `literal_eval` dos literais `_ENV`, `_NATURAL_CODE`, `_PATH_LIMIT`, `_COMMAND_LIMIT`, `MAX_TURNS` (`qual:44-56`) e `_PARK_SLICE_S` (`setup_probe:44`), iguais às constantes próprias do main e, para `MAX_TURNS`, ao valor do mesmo nome na entrada pinada.
   - `_LOCAL_PATH` (`qual:53`): exigir a forma EXATA de AnnAssign com valor `Call(Attribute(Name re).compile)`, um único argumento posicional `Constant str` e zero keywords; comparar esse literal com `_LOCAL_PATTERN` do main. Nunca `literal_eval` no `Call`.
   - Exigir que `_inputs` use `re.fullmatch(_LOCAL_PATTERN, …)`.
   - `ast.dump` da expressão de `_natural_command` igual à de `qual:291`, normalizando só o nome do operando de código.
5. **Carga** (árvore temporária com cópias):
   - pin ausente, adulterado, grande demais, diretório, reparse ou tamanho forjado → 3, sem execução;
   - mesmos bytes, verificados por troca do arquivo depois da captura;
   - nome bloqueado em `sys.modules` → 3;
   - registro presente durante o `exec` e removido depois, binding alheio intocado;
   - controle na carga → `None`, com o objeto exato em `holder.first_control`.
6. **Entradas:** argv fora do domínio → 2 via `_run_s`, sem leitura de arquivo.
7. **Fluxo pela costura, só casos DINÂMICOS alcançáveis:**
   - DONE → 0;
   - DONE_NONZERO → 10;
   - REFUSED → 11;
   - SETUP_REFUSED → 12, por falha limpa de criação do job no kernel falso, como no teste `1835`; não por Request inválido, porque as entradas já passaram pelo domínio de §2;
   - ACK_FAILED → 13;
   - RETAIN, incluindo controles retidos pela entrada → `None`, sem sobrescrever `custody.first_control`.
   - Identidades: Request exato de `adoption.Request`; `custody.request is holder.request`; `custody.adoption is holder.adoption`; portas `is`.
   - `capsys` vazio.
8. **Dados hostis no holder próprio** (sem fake entrada ou Owner):
   - `holder.entered = True` antes de `_enter` → `None`, zero chamadas ao kernel e zero lookups nas portas;
   - **custódia usada:**
     - Uma primeira `_enter` pela costura termina em RETAIN, com Owner real do SDK falso retido na custódia.
     - Recolocar `entered = False` como dado hostil e chamar `_enter` de novo devolve `None`.
     - Nenhuma chamada nova ao kernel, nenhum lookup de portas e `entered` continua False.
     - A custódia e o Owner são os MESMOS objetos, sem campo alterado.
   - **variantes do guard de custódia**, cada uma isolada sobre custódia própria fresca → `None`, sem efeito:
     - tipo diferente de `holder.entry.EntryCustody`;
     - `claimed` True;
     - `owner` não None;
     - `first_control` não None.
   - **Request de tipo errado:**
     - Dado hostil no holder, com custódia própria realmente fresca, sem Owner e sem controle.
     - A entrada real devolve REJECTED → 14, com zero chamadas ao kernel e a custódia intocada.
   - O contador de jobs do kernel é só evidência complementar, nunca contagem de invocações.
9. **Só estruturais** (sem cobertura dinâmica fabricada):
   - `Exception` escapando de `run_entry`;
   - controle na lacuna pós-retorno e na classificação;
   - controle em `_inputs`;
   - região externa de `main`.

**RED:** o root lê todos os oráculos, mede e congela o RED (falhas só por ausência da fonte) ANTES de pedir a fonte.

## 10. Limites honestos

**Não medidos por estes oráculos:**
- `main` e `_run_s` completos com argv válido e portas reais do interpretador;
- a composição deles além da estrutura;
- duração física de S e do park;
- binding real de stdin/stdout;
- ausência de escrita do interpretador em stderr;
- instante de saída e resíduos entre bytecodes;
- fechamento de C ou de handles;
- cleanup, descendentes, EOF de P e causalidade de LAST_CLOSE.

Ficam para inspeção estrutural e para provas físicas futuras observadas por H (XJ3 §8, §12), ainda não admitidas.

## 11. Fora deste contrato

- N-H (host v2, direitos R1–R3, duplicação, atenuação, `W1XJ1`) e o transporte vivo N-C do lado H.
- As fatias futuras são só uma proposta de ordem; não há máquina de H, host nativo, execução ou nova camada.
- Todos os gates nativos e de produto continuam OPEN. O Gateway segue indisponível.

## 12. Questões em aberto

Nenhuma. Orçamento, códigos de saída e fatia do park foram decididos sob delegação (SM-R1) e estão fechados em §4, §5 e §8.
