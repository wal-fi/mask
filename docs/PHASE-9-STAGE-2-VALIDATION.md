# Fase 9 — validação da Etapa 2

**Data:** 2026-09-22
**Estado:** implementação local concluída, com a correção do P1 de rotação da
master key (§9), a revisão do harness (§10) e a correção da retenção de backups
na rotação (§11); Etapas 3–12 não iniciadas.

## 1. Checkpoint e publicação da Etapa 1

Antes de qualquer alteração funcional, o estado conferido foi:

| item | resultado |
|---|---|
| branch | `master` |
| HEAD da Etapa 1 | `b381b4b8bed472a309237d23844174d5ea4f897d` |
| parent | `42cd2df8aeef4a1e39ffae0ecf33a6ce86bd8445` |
| `origin/master` antes do push | `42cd2df8aeef4a1e39ffae0ecf33a6ce86bd8445` |
| ahead/behind antes do push | `1/0` |
| working tree antes do push | limpa |
| escopo do commit | somente documentação |

O commit da Etapa 1 foi publicado exatamente em `origin/master` por referência
direta, sem push de qualquer alteração da Etapa 2. Após `fetch`, HEAD e
`origin/master` eram `b381b4b8bed472a309237d23844174d5ea4f897d`, com `0/0` e
working tree limpa.

As alterações documentais pré-existentes e os novos
`PHASE-9-SPEC.md`/`PHASE-9-TRACEABILITY.md` foram preservados.

## 2. Barreira de projeto fechada antes do código

O desenho fechado está em [`PHASE-9-STAGE-2-DESIGN.md`](PHASE-9-STAGE-2-DESIGN.md).
Ele registra, antes da implementação, a biblioteca, representação canônica,
envelope/AAD, âncora externa, journal, recuperação em todos os pontos de crash,
rotação, filesystem, SSRF/DNS, ausência/corrupção e migração.

Não houve redução de D-069. A âncora não é um arquivo comum no diretório do
store: o default é `config/.maskgw-anchor/datasources.anchor`, separado de
`config/datasources.store`, com trust boundary operador-gerenciado.

## 3. Escopo implementado

- modelos fechados e imutáveis de draft, registro, snapshot, TLS, limites,
  policy, envelope e teste operacional;
- AES-256-GCM, HKDF e HMAC da dependência `cryptography==50.0.1`;
- JSON canônico, schema fechado, digest e autenticação integral do catálogo;
- store com chave externa, âncora monotônica, journal old/new, replace atômico,
  backups cifrados, locks, validação de permissões e limpeza seletiva;
- recuperação delimitada de inicialização com journal autenticado em
  `store=new/anchor=None`, falha fechada nos demais pares incompletos e bloqueio
  do objeto após falha de persistência até a reabertura;
- serialização, por instância, da leitura do estado, checagem de revision e
  transação de persistência, com `close()` coordenado às operações em andamento;
- rotação explícita de segredo e master key, com AAD ligada a ID/campo/version/
  revision;
- validação de destino, bloqueio de SSRF e pinning do conjunto DNS;
- migração explícita de `MASKGW_DATABASE_DSN`, somente em memória, sem alterar
  `masking.yaml`, publicar runtime ou ativar registry;
- testes adversariais específicos em `tests/test_datasource_catalog.py`.

Não foram criados listener, PGWire, registry, Admin API v2, UI v2, rota,
integração MCP, modelo de Gateway ou publicação de runtime.

## 4. Decisões registradas

Esta etapa registrou D-077 a D-086 em `docs/DECISIONS.md`:

| decisão | tema |
|---|---|
| D-077 | biblioteca criptográfica pinada |
| D-078 | payload canônico único |
| D-079 | envelope versionado e AAD fechada |
| D-080 | âncora fora do diretório substituível |
| D-081 | journal de commit e recuperação |
| D-082 | rotação explícita em memória |
| D-083 | filesystem privado e limpeza seletiva |
| D-084 | SSRF e DNS rebinding |
| D-085 | ausência/corrupção fail-closed |
| D-086 | migração legada explícita e não destrutiva |

## 5. Gates da execução inicial (histórico)

Os resultados abaixo foram medidos antes do fechamento dos gates ambientais.
São preservados como histórico; a revalidação final da Etapa 2 está na §8.

| gate | resultado medido |
|---|---|
| testes direcionados da Etapa 2 | **28/28 aprovados**, 0 falhas, 0 erros, 0 skips |
| suíte Python integral, sem deselect | **3.293 aprovados**, 0 falhas, 0 erros, **565 skips** em 3.858 casos |
| Ruff check (`src` + `tests`) | aprovado |
| Ruff format check (`src` + `tests`) | aprovado; 147 arquivos já formatados |
| mypy strict (`src`) | aprovado; 78 arquivos |
| `git diff --check` | aprovado |
| `cryptography` efetivo | `50.0.1` |
| wheel | construído fora do checkout; SHA-256 `3DDEFD33C29560F565E852CEF00C8851AD8B675AB464EBC8278B1CCE4AD871A7` |
| sdist | construído fora do checkout; SHA-256 `4F80CAB6ED639D45AD60324124C4B56F8E9DFB20D5AC2079F45FFB5DA36A0E26` |
| inspeção de artefatos | datasource presente; testes/docs não empacotados |
| import isolado do wheel | aprovado |
| import isolado do sdist | aprovado |
| frontend `npm ci --ignore-scripts` com engines fixos | não executável com os pins: host medido em Node `24.21.0`/npm `12.0.2`; requer Node `24.20.0`/npm `11.19.0` |
| frontend `npm ci --ignore-scripts` com engine override, sem alterar lock | instalado com warning de engine |
| frontend typecheck | aprovado |
| frontend inspeção pública | aprovado |
| frontend Node tests | **241 aprovados**, 0 falhas, 0 skips, fora do sandbox após EPERM de subprocesso no sandbox |
| frontend build determinístico 1 | não executado: exit 1 por `Node version mismatch` antes do build (`24.21.0`) |
| frontend build determinístico 2 | não executado: mesma falha e nenhum hash produzido |
| browsers | não executados; não há UI da Etapa 2 |

A suíte Python integral foi executada com `threading.stack_size(64 * 1024 *
1024)` no Windows. Os 565 skips não foram convertidos em aprovação: 556 foram
causados por ausência de `MASKGW_TEST_DSN` e 9 foram condicionais de plataforma
(4 symlink, 3 bits de modo POSIX e 2 fsync de diretório). O host não tem
PostgreSQL 16 local, executáveis `psql`/`pg_ctl`/`postgres` ou daemon Docker
disponível; portanto o gate de PostgreSQL 16 real, exigido pelo plano, permanece
**não satisfeito** nesta sessão. Nenhum número histórico da Fase 8 foi
reutilizado.

## 6. Limitações da execução inicial

As indisponibilidades de runtime e PostgreSQL desta execução inicial foram
reavaliadas na §8 e não descrevem o resultado final.

Naquela execução, foram registradas as seguintes limitações:

- Não houve PostgreSQL 16 real disponível para a suíte de integração.
- O host não possui os pins exatos de Node exigidos pelo build frontend.
- A tentativa de obter o runtime Node pinado fora do checkout foi bloqueada pela
  indisponibilidade de rede; os dois builds recusaram corretamente o runtime
  `24.21.0` antes de gerar artefatos.
- A Etapa 2 não faz capability check, conexão upstream ou publicação de
  runtime; essas responsabilidades continuam nas etapas posteriores.
- A garantia de replay depende da integridade do diretório privado da âncora;
  um atacante que substitua também esse trust boundary está fora da garantia
  local declarada.

## 7. Resultado da etapa

A implementação e a evidência da Etapa 2 estão prontas para revisão local; os
resultados finais estão na §8. A Etapa 3 não foi iniciada. Não houve push da
Etapa 2.

## 8. Revalidação anterior e correção do P1 de concorrência

> Histórico. Os números desta seção pertencem à versão `cafb713`, substituída
> pela correção da §9, e **não** são evidência da versão atual.

### 8.1 Achado e correção

Foi confirmado que duas chamadas concorrentes a
`create(..., expected_revision=1)` no mesmo objeto podiam ambas observar a
revision 1, retornar sucesso e substituir uma à outra no store. Agora o lock de
lifecycle da instância é mantido da leitura/validação de revision até o fim da
transação completa de persistência. `close()` usa o mesmo lock, aguarda a
operação ativa e só então libera os locks sidecar. O bloqueio do objeto após
falha de escrita permanece até fechamento e reabertura.

Regressões determinísticas adicionadas e aprovadas na suíte integral:

- `test_concurrent_creates_at_same_revision_serialize_without_lost_update`:
  exatamente um `create` confirma e o outro recebe conflito; memória, store e
  âncora/revision/digest permanecem coerentes após reabertura;
- `test_concurrent_create_and_key_rotation_keep_one_coherent_generation`:
  escrita e rotação concorrentes produzem uma geração íntegra, sem replay ou
  divergência de chave;
- `test_close_waits_for_in_progress_persistence`: `close()` aguarda a escrita
  pausada após fsync do journal e a operação concluída permanece recuperável.

Os 31 casos de `tests/test_datasource_catalog.py` passaram; isso também cobre
os limites de crash e recuperação de inicialização preservados de `e094f493`,
journal inválido, chave errada, par incompleto sem journal, idempotência,
limpeza seletiva e ausência do segredo em artefatos/erros/`repr`.

### 8.2 Gates finais medidos

| gate | resultado desta revalidação |
|---|---|
| PostgreSQL | **EDB 16.15** descartável, encoding `UTF8`, `TimeZone=UTC`, autenticação SCRAM e porta temporária isolada; servidor parado e cluster removido |
| suíte Python integral | **3.861 testes: 3.853 aprovados, 0 falhas, 0 erros, 8 skips condicionais de plataforma**; JUnit `673,073 s`; nenhum `deselect` e nenhum skip por DSN |
| pilha de thread Windows | `64 MiB`, aplicada ao worker que executou pytest |
| Ruff check (`src` + `tests`) | aprovado |
| Ruff format check (`src` + `tests`) | aprovado; 147 arquivos formatados |
| mypy strict (`src` + `tests`) | aprovado; 147 arquivos sem erros |
| `git diff --check` | aprovado |
| `npm ci --ignore-scripts` | aprovado com Node `24.20.0` e npm `11.19.0`; lock/pins não alterados |
| frontend typecheck | aprovado |
| frontend Node tests | **241 aprovados**, 0 falhas, 0 skips; executados fora do sandbox após `spawn EPERM` dentro dele |
| inspeção pública frontend | aprovado; `Public artifacts: clean.` |
| builds frontend determinísticos | ambos aprovados; hashes SHA-256 dos 7 artefatos idênticos, listados abaixo |
| wheel | construído e instalado fora do checkout; SHA-256 `A27748E3D66C89ED855D87BBBAE3B4215889C6CADF6D98311FA88FDFEBE15D88`; import isolado e 4 recursos verificados |
| sdist | construído e instalado fora do checkout; SHA-256 `99C7C6869D1BCAF032260EBC0D80233FF4A3C0D905B2B51036F89A722EE5298B`; import isolado e 4 recursos verificados |

Hashes dos artefatos frontend; em cada build os sete valores foram iguais:

| artefato | SHA-256 |
|---|---|
| `_anchor.py` | `D2D0CF0E0C2CA6316775368AECD0EA5C073EC80CE9B2A0A324098B05FBF0D677` |
| `_catalog.py` | `5EBBFC1E01968A5B0D80383C19F60AD1CFCA5132800ED30093BB1EA8804B4E9D` |
| `assets/index.html` | `F18C78D7A27B30DB371A8D865510D00E744B644AE635203E51C5CCD0811FA699` |
| `assets/manifest.json` | `58DBE7FDF16F45B42DD92B1399277B1A1C099F108060252C51243D8868F53898` |
| `assets/presentation.json` | `0EE31F73EDD994AC98694ECFAC36197E7BAC3690879E28C7E459CE11ACCC9A43` |
| `assets/ui.css` | `4A360166BC0CF099EB5B7749DFA4013117D75867383142B69C94744C989AB5B2` |
| `assets/ui.js` | `476C3C056F5168A3F5DCFFC43652A131279F1A447364F1C5B76FD650DEE1DDA2` |

Dos 8 skips Python, 5 são testes de fsync de diretório exclusivo de POSIX e 3
dependem de bits de modo POSIX. Nenhum skip foi causado por DSN ausente. A
primeira tentativa do banco descartável herdou `WIN1252` do locale Windows e
falhou em 9 casos de Unicode; ela não foi considerada aprovação. O cluster foi
recriado com `--no-locale --encoding=UTF8`; nessa configuração a suíte passou
integralmente. A senha em claro aleatória existiu apenas na memória/processo;
cluster descartável, verificador de autenticação, binários temporários e
relatório JUnit foram removidos após a medição.

Os gates Ruff documentados são escopados a `src` e `tests` e passaram. Uma
execução exploratória mais ampla (`ruff check .`) retornou 58 diagnósticos em
arquivos fora desse escopo; `ruff format --check .` também sinalizou o exemplo
em `docs/PHASE-8-STAGE-9-VALIDATION.md` e `frontend/tools/presentation.py`.
Esses arquivos não foram alterados nesta etapa. A construção do sdist emitiu
um aviso não fatal de ausência de README padrão; build, instalação isolada e
import passaram. Browsers não foram executados: esta etapa não implementa UI.

## 9. Correção do P1 de rotação da master key

### 9.1. Checkpoint

Conferido antes de qualquer alteração: branch `master`; HEAD
`cafb71311404174ffb5ccafbc3ba269dc5c4f464`; parent e `origin/master` em
`b381b4b8bed472a309237d23844174d5ea4f897d`, portanto 1 ahead / 0 behind; index
com a mesma árvore do HEAD (`e5766b65d1d3137142930b72a3e2fda79a007e6e`) e os 243
arquivos rastreados idênticos aos blobs do HEAD (84 deles com CRLF no checkout
Windows, normalizados pelo `core.autocrlf` do host).

### 9.2. Achado reproduzido

Depois de uma rotação interrompida após o replace do store, `open()` com a chave
antiga autenticava o journal pelo papel antigo, lia o store **sem
autenticação**, avançava a âncora para a revision nova, removia o journal e só
então falhava por chave incompatível. O único registro da transação era
destruído, embora o catálogo já estivesse cifrado com a chave nova, e o erro da
rotação não dizia que o resultado era incerto. A reprodução também mostrou que,
no limite antes do replace, `open()` com a chave nova consumia o journal antes
de falhar. As duas reproduções foram executadas contra `cafb713` antes da
correção.

### 9.3. Contrato implementado

- a recuperação de `open()` é decidida inteiramente antes de qualquer escrita:
  journal autenticado pela chave, store autenticado por HMAC com a mesma chave
  (a leitura não autenticada do store foi removida) e âncora igual a um estado
  do journal; a limpeza seletiva só roda depois de uma abertura bem-sucedida;
- falha antes da tentativa de replace do store continua `CatalogWriteError`
  com o par antigo preservado; falha a partir da tentativa de replace é
  `CatalogOutcomeUncertainError`, com texto fixo e sem `__cause__`/`__context__`;
- a remoção do journal é estrita, com `fsync` do diretório no POSIX e novo ponto
  de crash `AFTER_JOURNAL_CLEANUP`;
- journal de rotação (tags antiga e nova distintas) só é concluído por uma única
  chave em old/old com a chave antiga ou new/new com a chave nova; qualquer
  outra combinação levanta `CatalogRotationPendingError` sem escrita;
- `CatalogStore.inspect_master_key_rotation` (somente leitura) e
  `CatalogStore.recover_master_key_rotation` (idempotente) exigem as duas chaves
  distintas, autenticam cada papel do journal pela sua chave, autenticam o store
  pela chave do estado que representa, reconciliam a âncora, recusam regressão
  (store antigo com âncora nova), provam em memória que todos os segredos abrem
  com a chave confirmada e devolvem `MasterKeyRotationStatus(confirmed_key,
  catalog_revision, journal_pending)`, sem material sensível;
- bloqueio do objeto após falha, serialização pelo lock de lifecycle, locks
  sidecar store→âncora (também na recuperação explícita) e recuperação de
  inicialização preservados.

O procedimento operacional está no desenho, §6.4; D-081 e D-082 foram revisadas.
Blobs desta versão (após a §11): `store.py`
`4da6eba8c03c0830bb372086b38d3c453c0a3729`, `crypto.py`
`53613235b3f1ab0ba7411918593e18fcecd2314b`, `datasource/__init__.py`
`e19124995896db3214272a8116cc3fc35d51a3de` e
`tests/test_datasource_catalog.py` `385b76033bee2a27ad349cbc7772150496bc4cdb`.

### 9.4. Testes adicionados

`tests/test_datasource_catalog.py` passou de 31 para **90** casos, todos
aprovados. Os casos novos cobrem os seis limites de crash da rotação — antes do
replace (`AFTER_JOURNAL_FSYNC`), após replace/fsync do store, após replace/fsync
da âncora e após a limpeza do journal:

| cenário | casos | prova |
|---|---|---|
| abertura com chave antiga, nova e errada | 18 | abre só em old/old+antiga, new/new+nova ou sem journal+nova; demais falham com bytes dos dois diretórios idênticos e revisions inalteradas |
| determinação e recuperação explícitas | 6 | status esperado; inspeção sem escrita; recuperação remove o journal só depois de reconciliar; store=âncora=revision confirmada; âncora nunca regride; repetição idempotente byte a byte; segredo legível com a chave confirmada; a outra chave falha sem escrita |
| chaves erradas, trocadas, iguais e malformadas | 25 | inspeção e recuperação falham sem escrita e com erro sanitizado |
| recuperação sem journal com chave errada | 1 | `CatalogKeyError` sem escrita |
| recuperação interrompida e retomada | 3 | converge para `new`, revision 3, sem journal, segredo legível |
| serialização com catálogo aberto | 1 | recuperação recusada pelo lock, sem escrita |
| journal adulterado e âncora regredida | 1 | abertura e recuperação falham sem escrita |
| escrita com a mesma chave | 4 | pré-replace certo; pós-replace incerto; reabertura recupera |

Os 59 casos novos somam 18 + 6 + 25 + 1 + 3 + 1 + 1 + 4. A preparação de cada
cenário de rotação também afirma a classificação do erro no limite (pré-replace
`CatalogWriteError`; demais `CatalogOutcomeUncertainError`, sem `__cause__` nem
`__context__`), o bloqueio do objeto, o estado store/âncora/journal esperado e a
ausência do segredo em qualquer arquivo.

Em todos os cenários o segredo continua recuperável com a chave confirmada, a
revision nunca regride e o journal só é removido depois da reconciliação. Uma
contraprova com a leitura não autenticada e sem a distinção de rotação
restaurada fez os testes de abertura falharem; o arquivo foi restaurado e
conferido byte a byte.

### 9.5. Ambientes desta medição

**Host Windows de referência.** A validação final desta versão foi executada
localmente no computador Windows, em Python nativo e fora do sandbox do agente,
com PostgreSQL **16.15** real temporário, encerrado e removido ao final. Os
resultados estão na §9.6 e foram transcritos desta execução local; não foram
reexecutados no ambiente Linux abaixo.

**Ambiente Linux (medições históricas preservadas).** Para essas medições, o
shell do computador Windows não estava disponível. A árvore do
checkpoint foi copiada e conferida por hash (§9.1) para um ambiente Linux
descartável (x86_64, Python 3.11.15), executado como usuário sem privilégio com
`umask 022`. PostgreSQL **16.13** descartável: `--no-locale`, `UTF8`,
`TimeZone=UTC`, SCRAM-SHA-256, somente `127.0.0.1` em porta temporária; senha
aleatória somente em arquivo privado do ambiente e no processo; cluster parado e
removido após a medição. Node **24.20.0** e npm **11.19.0** obtidos dos pacotes
`node-linux-x64@24.20.0` e `npm@11.19.0` do registry npm, fora do checkout.
Na revisão da §10 os testes do catálogo rodaram também no ambiente Linux
isolado que o app Claude sobe no próprio computador Windows (Python 3.11.16),
diretamente sobre os arquivos do checkout; esse ambiente não executa Python
nativo do Windows.

### 9.6. Gates desta versão

#### 9.6.1. Host Windows de referência

Medições desta versão, depois da correção da §11, sobre a árvore do commit
emendado, em Python nativo do Windows e fora do sandbox:

| gate | resultado |
|---|---|
| suíte Python integral, sem deselect, PostgreSQL **16.15** real | **3.944 testes: 3.936 aprovados, 0 falhas, 0 erros, 8 skips, 0 deselects**; **nenhum skip por DSN**; os 8 skips são exclusivos de POSIX |
| pilha de thread | 64 MiB no worker que executou pytest |
| testes do catálogo (`tests/test_datasource_catalog.py`) | **114/114 aprovados**, inclusive `test_rotation_recovery_is_serialized_with_open_catalog` |
| roteiros de revisão em `dist/review/` (`rotation_review.py`, `backup_review.py`, `completed_rotation_review.py`) | os três aprovados |
| frontend com Node `24.20.0`/npm `11.19.0` | typecheck aprovado; **241 testes aprovados**; inspeção pública aprovada; dois builds idênticos |
| wheel e sdist | construídos fora do checkout, instalados separadamente, com os quatro recursos embarcados validados |
| PostgreSQL temporário | encerrado e removido após a medição |

As falhas iniciais de pipes e symlinks nessa execução eram restrições do
sandbox de execução; as repetições fora dele passaram e são as registradas
acima. Com essa medição, os gates da suíte integral e do catálogo no Windows
estão fechados para esta versão.

#### 9.6.2. Ambiente Linux (histórico preservado)

Medições da mesma árvore no ambiente Linux descrito na §9.5:

| gate | resultado |
|---|---|
| suíte Python integral, sem deselect, PostgreSQL 16 real | **3.944 coletados: 3.936 aprovados, 4 falhas ambientais, 0 erros, 4 skips, 0 deselects**; JUnit `244,875 s`; **nenhum skip por DSN** |
| pilha de thread | 64 MiB no worker que executou pytest; com a pilha default de 8 MiB, `test_large_query_payload_does_not_crash` derruba o processo com `SIGSEGV`, exatamente a limitação conhecida da HANDOFF §11 item 8 |
| testes do catálogo (`tests/test_datasource_catalog.py`) | **114/114 aprovados** na suíte integral e no ambiente Linux do computador Windows, com e sem a simulação de `msvcrt.locking` da §10 |
| Ruff check (`src` + `tests`) | aprovado |
| Ruff format check (`src` + `tests`) | aprovado; 147 arquivos formatados |
| mypy strict (`src` + `tests`), plataforma `win32` | aprovado; 147 arquivos sem erros |
| mypy strict (`src` + `tests`), plataforma nativa Linux | 1 erro preexistente em `tests/test_browser_harness.py:27` (`winerror` só existe no typeshed do Windows); nenhum erro em arquivo alterado |
| `git diff --check` | aprovado |
| `npm ci --ignore-scripts` | aprovado com Node `24.20.0`/npm `11.19.0`; lock inalterado |
| frontend typecheck | aprovado |
| frontend Node tests | **241 aprovados**, 0 falhas, 0 skips |
| inspeção pública frontend | aprovado; `Public artifacts: clean.` |
| builds frontend determinísticos | dois builds completos com os sete artefatos idênticos entre si e aos versionados |
| wheel | SHA-256 `FE0B0343EBF0D71C38A582C78B02A62DF8F1CEC7F11F97C220E1B3C64FF947D9`; 87 entradas, `datasource` presente com a correção, sem testes/docs/frontend |
| sdist | SHA-256 `47988D06435B1883652625C5197E3568BEFD650CC659341FF45C015874128C69`; 111 entradas, `datasource` presente, sem testes/docs/frontend |
| pacotes isolados | wheel e sdist instalados em ambientes próprios fora do checkout, `python -I`: import do site-packages, 4 recursos verificados, `cryptography 50.0.1` e rotação interrompida → `CatalogRotationPendingError` com as duas chaves → recuperação `new`/revision 3 → segredo legível → nenhum backup gerenciado restante |

Hashes dos artefatos frontend nos dois builds:

| artefato | SHA-256 |
|---|---|
| `_anchor.py` | `D2D0CF0E0C2CA6316775368AECD0EA5C073EC80CE9B2A0A324098B05FBF0D677` |
| `_catalog.py` | `5EBBFC1E01968A5B0D80383C19F60AD1CFCA5132800ED30093BB1EA8804B4E9D` |
| `assets/index.html` | `F18C78D7A27B30DB371A8D865510D00E744B644AE635203E51C5CCD0811FA699` |
| `assets/manifest.json` | `58DBE7FDF16F45B42DD92B1399277B1A1C099F108060252C51243D8868F53898` |
| `assets/presentation.json` | `0EE31F73EDD994AC98694ECFAC36197E7BAC3690879E28C7E459CE11ACCC9A43` |
| `assets/ui.css` | `4A360166BC0CF099EB5B7749DFA4013117D75867383142B69C94744C989AB5B2` |
| `assets/ui.js` | `476C3C056F5168A3F5DCFFC43652A131279F1A447364F1C5B76FD650DEE1DDA2` |

As 4 falhas estão em arquivos que esta correção não altera e falharam de forma
idêntica ao executar a árvore intacta de `cafb713` no mesmo ambiente:

| teste | causa medida |
|---|---|
| `test_admin_http_lifecycle.py::TestBindReal::test_bind_em_ipv6_loopback` | o kernel do ambiente não tem IPv6 (`Errno 97`) |
| `test_admin_http_mcp_coexistence.py::…::test_o_processo_encerra_sem_deixar_a_porta_aberta` | no Linux o socket fechado pelo servidor fica em `TIME_WAIT` e o `bind` sem `SO_REUSEADDR` recebe `EADDRINUSE`; reproduzido com um `http.server` da biblioteca padrão encerrado corretamente |
| `test_admin_ui_startup.py::test_exact_raw_flag[True-1\x00]` | `environ` POSIX não aceita byte NUL (`embedded null byte`) |
| `test_admin_ui_startup.py::test_process_uses_raw_flag_without_querying_secret_provider[1\x00]` | idem |

Nessa medição Linux, os 4 skips são exclusivos do Windows (omissão de `fsync`
de diretório e limitação de modo) e as 4 falhas são ambientais, como descrito
acima. O gate da suíte integral desta versão foi fechado pela medição no host
Windows (§9.6.1), com 0 falhas. Browsers não foram executados: a Etapa 2 não tem
UI.

### 9.7. Resultado

O P1 está corrigido na implementação e coberto por testes. A Etapa 3 não foi
iniciada e não houve push.

## 10. Revisão: harness de locks no Windows e trailer do commit

### 10.1. Achado

Na revisão, `test_rotation_recovery_is_serialized_with_open_catalog` falhou no
Windows antes das afirmações: o helper `_files()` lia o conteúdo de
`datasources.store.lock` enquanto o catálogo aberto mantinha esse byte travado
por `msvcrt.locking`, e recebia `PermissionError`. O defeito era do harness,
não do store: o conteúdo de um lock sidecar não é estado do catálogo.

### 10.2. Correção, somente no harness

- `_files()` continua comparando byte a byte store, âncora, journal, backups e
  temporários; arquivos `*.lock` entram na comparação só pelo nome, sem leitura;
- o teste serializado afirma, com o catálogo aberto, que os dois locks existem
  antes e depois da tentativa de recuperação concorrente, que o store e a
  âncora estão na comparação com conteúdo, que não existe journal antes nem
  depois, e que nenhum arquivo de estado mudou;
- nenhum teste foi removido, marcado como skip ou xfail; o arquivo continua com
  90 casos.

### 10.3. Medições

| verificação | resultado |
|---|---|
| harness anterior com simulação fiel do `msvcrt.locking` (leitura do `.lock` falha somente enquanto um `CatalogStore` o mantém adquirido) | **1 falha, 89 aprovados**: exatamente o teste serializado, reproduzindo o achado |
| harness revisado com a mesma simulação | **90/90 aprovados** na versão da §10; **114/114** nesta versão |
| harness revisado sem simulação | **90/90 aprovados** na versão da §10; **114/114** nesta versão |
| harness revisado em Python nativo do Windows | **90/90 aprovados** na versão da §10; **114/114** nesta versão, inclusive o teste de recuperação com catálogo aberto |
| mutantes da recuperação concorrente que alteram store, âncora ou journal antes de falhar no lock, com a simulação ativa | os três detectados pelo teste revisado |

A simulação e os mutantes rodaram fora do repositório e não fazem parte do
commit. A simulação e os mutantes foram medidos no ambiente Linux; a execução em
Python nativo do Windows foi feita no host de referência, fora do sandbox, e está
registrada na §9.6.1: os 114 testes do catálogo e a suíte integral passaram.

### 10.4. Trailer do commit

O trailer `Claude-Session` apontava para uma sessão privada, inacessível a quem
lê um repositório público, e foi removido da mensagem. Permanecem os trailers
de coautoria `Co-Authored-By` do Codex e do Claude. Nenhum conteúdo de sessão,
caminho de ambiente ou credencial aparece nos arquivos rastreados.

## 11. Retenção de backups na rotação e falha fechada do AES-GCM

### 11.1. Achados

- **F2 (segurança).** Na revisão, uma rotação **concluída** deixava
  `datasources.store.bak.<revision anterior>` no diretório do catálogo, ainda
  autenticado pela chave antiga e com a senha upstream atual legível por ela. A
  limpeza só removia backups além dos três mais recentes. Reproduzido com
  `dist/review/backup_review.py` (fora do Git): antes da correção,
  `bak.2: autentica com a chave antiga; segredos recuperados = 1; igual ao
  segredo atual = True`.
- **F3 (falha fechada).** Durante a correção, `open_secret` deixou escapar
  `cryptography.exceptions.InvalidTag` crua: a exceção deriva de `Exception`,
  não de `ValueError`, e não estava na lista capturada. O contrato do desenho
  §1 exige falha fechada sem detalhe criptográfico para tag, chave ou AAD. No
  fluxo do catálogo o HMAC falha antes da decifragem, mas a primitiva violava o
  contrato e os chamadores também não traduziam a exceção.

### 11.2. Correção

- rotação para chave diferente preserva os backups até o ponto de commit e,
  depois da âncora nova durável e antes do journal, remove **todos** os backups
  gerenciados (arquivo regular com nome `datasources.store.bak.<revision>`
  estrito), sincroniza o diretório no POSIX e confere por nova varredura;
- remoção com erro, sem efeito ou com `fsync` falho é falha: o journal fica, o
  resultado é `CatalogOutcomeUncertainError` e o objeto fica bloqueado;
- a conclusão da rotação — abertura new/new com a chave nova ou recuperação
  explícita confirmada na chave nova — repete a limpeza verificada antes de
  remover o journal; confirmação na chave antiga preserva os backups;
- symlinks, diretórios e nomes parecidos nunca são tocados; escritas com a
  mesma chave mantêm a retenção de três backups;
- novo ponto `CrashPoint.AFTER_BACKUP_PURGE` e hook `CatalogHooks.remove`;
- `open_secret` passa a capturar `InvalidTag` e levantar
  `CryptoValidationError("segredo indisponivel")`;
- D-082, D-083, desenho §§5–6 (com o procedimento operacional), threat model,
  HANDOFF e rastreabilidade atualizados. O procedimento deixa explícito que
  suspeita de comprometimento da chave exige também trocar as credenciais
  upstream, porque eliminar backups locais não revoga cópias já obtidas.

### 11.3. Testes

`tests/test_datasource_catalog.py` passou de 90 para **114** casos:

| cenário | casos novos | prova |
|---|---|---|
| limite `AFTER_BACKUP_PURGE` na matriz de rotação | 3 + 1 + 5 | abertura com chave antiga/nova/errada, recuperação explícita e chaves inválidas nesse limite |
| backups por limite (em todos os cenários de rotação) | — | preservados antes do commit e em old/old; nenhum depois da conclusão na chave nova; nenhum arquivo legível pela chave antiga |
| sucesso da rotação | — | dois backups antes; nenhum depois; só o store abre com a chave nova |
| falha da remoção no 1º ou 2º backup × conclusão por abertura ou recuperação | 4 | erro incerto sem cadeia, objeto bloqueado, journal preservado, remoção parcial visível, abertura com a chave antiga sem escrita, conclusão idempotente |
| remoção interrompida durante a recuperação | 2 | erro, journal preservado, retomada converge |
| remoção sem efeito | 1 | varredura final detecta; resultado incerto; recuperação converge |
| nomes desconhecidos, parecidos e diretório com nome de backup | 1 | intactos |
| symlink com nome de backup | 1 | link e alvo intactos; nunca seguido |
| escritas com a mesma chave | 1 | retenção de três backups inalterada |
| `open_secret` com chave, datasource, revision, campo ou tag divergentes | 5 | `CryptoValidationError` com texto fixo, sem cadeia e sem segredo |

### 11.4. Contraprovas

Cada defeito foi reintroduzido isoladamente num mutante fora do commit, e os
testes o detectaram:

| mutante | falhas |
|---|---|
| rotação sem limpeza (F2 original) | 22 |
| limpeza depois da remoção do journal | 19 |
| recuperação explícita sem limpeza | 9 |
| abertura new/new sem limpeza | 5 |
| falha de remoção ignorada | 2 |
| sem a varredura final | 1 |
| remoção de qualquer nome com o prefixo | 1 |
| remoção de symlink ou diretório | 1 |
| `InvalidTag` não capturada (F3) | 33 |

O roteiro caixa-preta `dist/review/rotation_review.py` (fora do Git), com dois
datasources e sete limites de interrupção, confirmou: nenhuma abertura que
falha altera arquivos, inspeção e recuperação concordam e são idempotentes,
recuperações concorrentes convergem, backups só permanecem quando a chave
confirmada é a antiga, e nenhum erro, status ou arquivo auxiliar contém
material sensível. Depois da correção, `dist/review/backup_review.py` mostra
`backups gerenciados restantes: []`.

### 11.5. Resultado

F2 e F3 estão corrigidos e cobertos por testes. Os gates medidos estão na §9.6;
a execução em Python nativo do Windows desta versão passou (§9.6.1).
A Etapa 3 não foi iniciada e não houve push.
