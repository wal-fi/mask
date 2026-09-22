# Fase 8 — Evidência da Etapa 9

**Estado:** Fase 8 concluída; Etapas 1–9 revisadas, aprovadas e publicadas em
`42cd2df`.
**Fechamento:** 2026-09-21.

**Nota posterior (2026-09-22):** a Etapa 1 documental da Fase 9 foi autorizada.
Isso não altera código, resultados ou evidências registrados neste fechamento.

## Checkpoint e publicação

Confirmados master, HEAD `20db6f021533230d791cd910b037554c3fe03191`,
origin/master e parent `57cc7522642d3fe3dddd10187b996ba71fc38e3f`, árvore limpa,
1 ahead / 0 behind, autor/committer `w.filho <w.filho@live.com>` e trailer
`Co-Authored-By: Codex <noreply@openai.com>`.
Publicado exatamente o commit aprovado da Etapa 8, sem amend, rebase ou edição.
O fetch confirmou HEAD igual a origin/master, 0/0, árvore limpa e metadados
preservados. Naquele checkpoint histórico, a Etapa 9 deveria permanecer em
um único commit para revisão, com publicação dependente de nova autorização.
Essa revisão foi aprovada e a publicação final está agora autorizada.

## Escopo

Verificação do pacote instalado e fechamento de §§6.2–6.8 e 7.2–7.3.
Nenhuma expansão funcional ou nova dependência é autorizada. Findings de produto
exigem contraprova antes da correção. Evidências históricas serão preservadas.

## Gates e critérios

As medições abaixo são desta rodada (2026-09-16 a 2026-09-21), não da baseline anterior.
A primeira matriz completa teve um timeout preservado abaixo; a repetição
integral passou. Todos os gates e critérios de aceite foram concluídos, com
os limites explícitos desta evidência.

| Gate | Resultado medido | Tempo |
|---|---|---|
| npm ci --ignore-scripts | exit 0; lockfile v3 e pins intactos | 49,25 s |
| build 1 / build 2 | exit 0; 14 saídas idênticas entre si e à Etapa 8 | 111,33 / 53,12 s |
| checkJs strict/noEmit | exit 0 | 18,31 s |
| inspeção pública | exit 0; 193 termos e literais decodificados | 6,62 s |
| Node | 241 aprovados; zero falhas/skips/cancelados; inclui 12 contraprovas de tipagem | 131,16 s; runner 129.578,1475 ms |
| Python completo | 3.830 coletados; 3.822 aprovados; oito skips POSIX; zero falhas/erros | processo 891,16 s; JUnit 863,941 s |
| Ruff | exit 0 | 1,03 s |
| format check | exit 0 | 1,25 s |
| mypy strict | exit 0; 140 arquivos | 12,62 s |
| wheel: integridade/CLI | dez recusas pré-efeitos, MCP stdio + HTTP e restart aprovados, com controles positivos pré/pós-restauração | 29,03 s |
| sdist: integridade/CLI | mesmas provas aprovadas, com controles positivos | 41,88 s |
| foco Chromium instalado | quatro cenários novos/ampliados aprovados | 61,72 s |
| wheel: matriz integral final | 195/195 aprovados, 65 por engine; zero falhas/skips/retries | 2.507,66 s |
| sdist E2E | nove aprovados, três por engine; zero falhas/skips/retries | 263,30 s |
| git diff --check | exit 0; revisão documental e escopo aprovados | sem cronometragem |

A primeira medição frontend também passou (npm ci 8,56 s; builds 43,05/32,30 s;
tipagem 7,64 s; inspeção 1,42 s; Node 73,38 s). A tabela registra a repetição
com os marcadores finais; ambos os recibos e os 14 hashes foram preservados.
A primeira suíte Python também passou com as mesmas contagens (517,50 s;
JUnit 509,230 s). Após reforçar os controles positivos da sondagem instalada,
a suíte integral e os verificadores foram repetidos; a tabela registra esta
medição final. As duas execuções mantêm apenas os oito skips POSIX.

O PostgreSQL de cada execução foi 16.15 real, imagem local postgres:16-alpine,
container descartável, porta aleatória publicada exclusivamente em 127.0.0.1,
credencial efêmera em ambiente. Sem DSN do projeto, filtro, deselect ou skip por
falta de DSN. O pytest rodou em thread com pilha temporária de 64 MiB (D-041).

Ferramentas fixadas: Node 24.20.0, npm 11.19.0, TypeScript 5.9.3,
@types/node 24.0.0, Playwright 1.63.0. Engines requeridos: Chromium
153.0.8010.12 / revisão 1243; Firefox 155.0 / 1543; WebKit 26.6 / 2359.
A versão efetiva de cada browser é conferida pelo harness a cada cenário.

## Distribuição e isolamento

Construção em diretório temporário externo, a partir de src, pyproject.toml e
MANIFEST.in; sem instalar ou alterar dependências. Backend existente:
setuptools 68.2.2, wheel 0.45.1, packaging 24.2.

| Artefato | Entradas | Bytes | SHA-256 |
|---|---:|---:|---|
| maskgw-0.1.0-py3-none-any.whl | 81 | 203524 | 04436244199b01f20feff9442e1f7311c603be8d4c00141736541c4745177dfb |
| maskgw-0.1.0.tar.gz | 104, incluindo diretórios | 172432 | f4d4dd1da738afd598f2c2f2139a0bae6a38e5d60d5f2c29f5aa1dbf93e60478 |

Dois venvs independentes foram criados fora do checkout. As dependências Python
já instaladas na baseline foram copiadas offline, preservando suas versões;
maskgw foi instalado de cada artefato com --no-index --no-deps
--no-build-isolation --no-compile. Não há fallback ao venv ou src do checkout,
instalação editável, Node/npm no PATH da aplicação ou ferramenta frontend no
pacote. O harness privado usa pytest e os clientes já existentes para observar
os efeitos; ele fica em diretório externo separado, nunca no wheel/sdist.

Python 3.11.3; versões de runtime conferidas: mcp 2.1.1, pglast 8.4,
psycopg/psycopg-binary 3.3.4, pydantic 2.13.5, PyYAML 6.0.3,
FastAPI 0.141.1 e uvicorn 0.52.4. A listagem completa das distribuições foi
registrada no recibo local de empacotamento, sem nova resolução de versões.

`installed_support.verify_environment` exige -I, prefixo/sys.path fora do
checkout e origem de todos os módulos maskgw dentro do site instalado, antes
e depois de cada filho. Em cada instalação quatro contraprovas recusaram:
site do checkout, site incorreto, Python sem -I e Node disponível no PATH.
A cópia de dependências conserva somente o .pth de bootstrap PyWin32 relativo
à instalação; caminhos editáveis do checkout são excluídos.

As distribuições não contêm frontend/, testes, fixtures, tipos .d.ts,
sourcemaps, node_modules, venv, secrets ou caches Python. O sdist não contém
links simbólicos/hardlinks. O catálogo e a âncora Python são parte necessária
do produto; a apresentação privada permanece autenticada. Arquivos de teste
e ferramentas de build/frontend não são recursos servidos.

## Recursos e inventários fechados

| Recurso | Bytes | MIME | Limite | SHA-256 |
|---|---:|---|---:|---|
| index.html | 351 | text/html; charset=utf-8 | 16384 | f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699 |
| ui.js | 112807 | text/javascript; charset=utf-8 | 524288 | 476c3c056f5168a3f5dcffc43652a131279f1a447364f1c5b76fd650dee1dda2 |
| ui.css | 1682 | text/css; charset=utf-8 | 65536 | 4a360166bc0cf099eb5b7749dfa4013117d75867383142b69c94744c989ab5b2 |
| presentation.json | 39704 | application/json | 262144 | 0ee31f73edd994ac98694ecfac36197e7bac3690879e28c7e459ce11accc9a43 |

Manifesto: SHA-256
`58dbe7fdf16f45b42dd92b1399277b1a1c099f108060252c51243d8868f53898`,
quatro entradas fechadas, limite de 16384 bytes. Âncora e catálogo instalados
iguais aos aprovados. Os 14 hashes de geração não mudaram; a Etapa 9 não
modificou fontes de produto, recursos, catálogo, gramática, schemas ou pins.

A igualdade integral não é checagem de subconjunto:

- 110 modelos (máximo normativo 128), 19 chamadas, seis vistas, oito editores;
- 48 controles, 56 bindings, 25 mensagens e format 1;
- oito leituras, uma validação sem escrita e exatamente dez escritas;
- dez escritas: adoção, reorder de regras, criar/editar/excluir regras,
  criar/editar/excluir exceptions, PUT database e PUT sql;
- nenhum PUT /config originado pela UI ou reorder de exceptions;
- HTTP UI off: 20 entradas / 28 pares método-caminho; UI on: 24 / 36.

`test_phase8_final_inventory.py` sela cada seção inteira, inclusive controles
aninhados, confronta bytes privado/embarcado e fornece 21 contraprovas
(remoção, alteração e raiz desconhecida para sete seções). Os validadores e
catálogos existentes continuam responsáveis pela conformidade semântica.
`package.spec.js` verifica os bytes HTTP, MIME, no-store, autenticação da
apresentação e os 193 termos nos recursos públicos/literais decodificados.
Isso não promete sigilo contra inferência ou acesso ao pacote instalado.

## Revisão adversarial, lifecycle e separação de planos

A matriz de encerramento em PHASE-8-TRACEABILITY.md liga os 65 requisitos
normativos aos testes acumulados e ao pacote instalado. A revisão mantém:

- Host/origem/Referer/Fetch Metadata exatos; CSRF, preflight, aliases, portas,
  opaque origin, DNS rebinding, duplicados e forwarding forjado recusados;
- inventário de rotas fechado, sem CORS/docs/diagnóstico/fault injection;
  HEAD, query, encoding, traversal, métodos e headers conforme §5.3–5.4;
- zero chamada administrativa antes de login; antes da validação de hash e
  gramática somente a apresentação permitida; metadata hostil não libera API;
- todo texto administrativo inerte, inclusive persistido e reaberto em outra
  sessão; controles positivos de execução/rede nos testes acumulados;
- token só no Authorization autorizado; sem stores, cookies, URL, logs,
  mensagens, DOM persistente, trace, HAR, vídeo ou screenshots administrativos;
- logout/401/reload/pagehide/pageshow/BFCache invalidam geração e conteúdo;
  respostas tardias não restauram sessão, rascunho ou validação;
- base/revision/rascunho, uma pendência e confirmação explícita; nenhum
  autosave, fila, retry, rebase ou rollback automático;
- conflito/busy preservam rascunho; resultado desconhecido e durabilidade
  incerta bloqueiam novas escritas; readback não atribui autoria por revision;
- candidata de validação preserva exceptions/proteções e não persiste;
  SQL somente aditivo, sem casefold autoritativo em JS ou allowed_pg_functions
  em mutações; IDs e revision somente leitura;
- fronteiras HTTP, persistência, runtime, auditoria e MCP sem alteração.

As provas adicionais verificam edição externa após validar e antes de gravar,
conflito entre abas depois da validação, igualdade de todos os inventários e
rollback operacional. Cada escrita real continua instrumentada para observar
arquivo, snapshot/runtime, digest, IDs, revision e auditoria existente. A edição
externa acrescenta um comentário aos bytes do YAML após validar: mesmo sem
mudar a semântica, a divergência de digest deve bloquear o commit. Controles
de falha só no harness privado, via stdin; nenhum endpoint novo.

No pacote instalado, dez recusas por instalação removem ou corrompem os quatro
recursos e manifesto reais. Contadores recusam acesso a arquivo de configuração,
lock, conexão, thread, socket e MCP; exit 1 e stderr exatamente
`maskgw: falha na inicializacao\n`, stdout vazio. Os bytes são restaurados em
finally e a validação positiva se repete. O controle positivo exige alcançar a
barreira de configuração com os recursos íntegros; assim, settings inválidos
não podem mascarar uma ausência de checagem dos assets. Hashes reancorados incompatíveis,
limites, UTF-8 e ownership imutável continuam cobertos pela suíte Python inteira.

A CLI instalada real, sem harness no processo do produto, mantém sessão MCP
stdio enquanto atende HTTP. O masking é comprovado por query do harness via
MCP; não existe controle SQL na UI. Shutdown seguido de restart no mesmo
arquivo/porta confirma liberação de lock/socket; stdout permanece protocolar.

## Rollback operacional

Depois de adoção, reorder, database e SQL, o harness reinicia com valor bruto 0:
as quatro rotas não existem, Origin é recusado e o cliente nativo continua
lendo a revision persistida. Reinicia então com 1 e autentica novamente.
Compara arquivo e backup byte a byte, snapshot/documento/IDs/revision e os
mesmos efeitos MCP em ambos os modos. A matriz Python off compara headers,
corpos e erros da Fase 7 e rejeição por presença de Origin/Referer.
Desabilitar a UI não desfaz qualquer operação persistida. Recuperação de
resultado desconhecido/durabilidade incerta permanece humana, fora da UI.

## Tentativas e limitações

A primeira tentativa de montar a árvore de build incluiu README.md, inexistente
neste projeto, e parou antes de construir artefatos. A lista foi corrigida para
os arquivos reais, sem criar README nem alterar o produto.

As primeiras sondagens instaladas (wheel 9,64 s; sdist 7,86 s) falharam ao
importar pywintypes. A causa foi reproduzida e localizada no harness: a cópia
offline excluía todo .pth, incluindo pywin32.pth, que adiciona win32/lib e o
bootstrap da dependência Windows existente. Copiar esse arquivo relativo
original, sem versão nova, permitiu repetir e aprovar ambas as sondagens.
As tentativas e seus logs foram preservados, não convertidos em skip/xfail.
As sondagens intermediárias sem os controles positivos adicionais haviam
passado em 25,91 s (wheel) e 38,36 s (sdist); a tabela registra as reforçadas.
Durante a revisão foi reforçada a sondagem com controles positivos antes e
depois de cada arquivo, mantendo os resultados das execuções anteriores.
Nenhum finding de produto foi reproduzido nesta revisão; nenhuma correção
funcional foi feita. Não se atribui causa a falhas intermitentes sem prova.

Oito skips legítimos e preexistentes, exclusivamente condicionais de plataforma:

- test_admin_adversarial.py:431, test_admin_http_audit.py:591,
  test_admin_http_writes.py:966, test_admin_service.py:910 e
  test_config_filesystem.py:465: fsync de diretório POSIX;
- test_config_filesystem.py:121, :129 e :140: bits de modo POSIX.

Nenhum skip por DSN, deselect ou finding. O warning preexistente pytest sobre
match="" permanece, sem silenciamento. Não se alega fsync POSIX nativo no
Windows: a prova pós-commit usa falha injetada depois do replace real.

BFCache: eventos persisted e retorno pelo histórico nos três engines;
restauração nativa adicional comprovada apenas no Chromium, na fixture elegível.
A automação fixada de Firefox/WebKit mantém a limitação histórica; não alegar
BFCache nativo nesses dois. Acessibilidade é verificada por teclado, foco,
labels, viewport 320 px, escala 200% e reduced motion; sem auditoria manual
externa ou certificação. Riscos aceitos de processo/extensão/navegador
comprometidos e findings históricos de outras fases não são encerrados aqui.

### Primeira matriz integral de navegador

A execução instalada no wheel terminou em 2.569,23 s com 194/195 aprovados:
Chromium 65/65, Firefox 64/65 e WebKit 65/65. O único desfecho não aprovado
foi timeout de 60.016 ms no caso de reorder concorrente entre duas abas do
Firefox. O último marcador disponível era a criação da página (11.241 ms);
não havia localização suficiente para atribuir causa. Não se alteraram timeout,
retry, produto ou critério de aprovação.

Foram acrescentados apenas marcadores estáticos de entrada, adoção, abertura
da aba, prontidão, rascunho e validação. O reporter aceita somente esses enums,
sem DOM, token, URL, corpo ou mensagem remota. O diagnóstico isolado e a
repetição integral ficam registrados separadamente. O diagnóstico Firefox
isolado passou em 24,88 s de gate (22.004 ms no caso), com todos os marcadores
e fechamento limpo; isso não estabelece a causa do timeout. Nenhum resultado parcial
substitui a matriz completa nem elimina o histórico da falha.

### Matriz integral final

A repetição completa do wheel instalado aprovou 195/195 em 2.507,66 s:
Chromium 65/65, Firefox 65/65 e WebKit 65/65; zero falhas, skips ou retries.
Os 195 casos registraram o fechamento do navegador e do subprocesso privado.
A aprovação não estabelece a causa do timeout anterior. Nenhuma mudança de
produto, timeout ou política de retry foi feita entre as duas matrizes.
O sdist aprovou separadamente nove fluxos, três por engine, em 263,30 s.

Conferência posterior: os 14 hashes continuam iguais ao recibo e ao HEAD da
Etapa 8, inclusive recursos/âncora/catálogo restaurados nas duas instalações.
O diretório de resultados do browser contém somente `.last-run.json`, sem
trace, HAR, imagem, vídeo ou documento administrativo.
A conferência final não encontrou subprocessos Python/Node do harness instalado
nem containers da Etapa 9 remanescentes. O runner removeu os containers descartáveis.

## Reprodução e registros

Registros locais: `%TEMP%/maskgw-phase8-stage9-gates/` contém scripts de gate,
recibos JSON, logs sanitizados de browser, JUnit e inventários das distribuições.
As tentativas iniciais foram mantidas com nomes distintos. Não são recursos do
produto nem substituem os testes versionados. Comandos principais:

```text
npm ci --ignore-scripts
npm run build                 # duas vezes; comparar os 14 hashes e HEAD
npm run typecheck
npm run inspect
npm test
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy --strict src tests
```

No Windows o comando Python integral é executado em thread de teste:

```python
import threading, pytest
results = []
threading.stack_size(64 * 1024 * 1024)
worker = threading.Thread(target=lambda: results.append(
    pytest.main(["-q", "-ra", "--junitxml=pytest.xml"])))
worker.start()
worker.join()
raise SystemExit(results[0] if results else 1)
```

O harness instalado recebe MASKGW_BROWSER_PYTHON (Python do venv externo),
MASKGW_BROWSER_ROOT (raiz externa dos testes privados), MASKGW_INSTALLED_SITE,
MASKGW_CHECKOUT e MASKGW_TEST_DSN. Estes são controles de teste, não settings
novos do produto. O filho usa -I, elimina PYTHONPATH e reduz PATH a System32;
o processo de produto nunca depende do Node usado pelo runner de desenvolvimento.
A sondagem instalada executa tests.installed_package_probe com esse Python.

A matriz completa usa `playwright test --config=frontend/playwright.config.js`,
com workers 1, retries 0 e os três projetos. O gate adicional do sdist seleciona
os fluxos completos e a inspeção HTTP; essa seleção não é apresentada como
segunda execução integral de todos os componentes.

## Critérios de aceite de §7.2

Todos os gates completos passaram nesta rodada. As aprovações abaixo mantêm
os limites explícitos de plataforma, BFCache, acessibilidade e riscos aceitos.

| Critério | Evidência concreta | Resultado final |
|---|---|---|
| Inventários exatos | Selo integral das sete seções/21 contraprovas, catálogo UI e matriz HTTP 20/28–24/36 | Aprovado |
| UI off preserva Fase 7 | Fixture byte a byte e rollback instalado | Aprovado |
| UI on sem CORS/origens externas | Matriz HTTP/CSRF e Fetch real nos três engines | Aprovado |
| Divisão público/privado | Metadata autenticada/hash/gramática e 193 termos em bytes HTTP instalados | Aprovado |
| Token/dados não persistidos | Sentinelas, lifecycle, stores vazios e ausência de artefatos administrativos | Aprovado |
| Fluxos/desfechos completos | Componentes + E2E real CRUD/reorder/DB/SQL/adoção/validação, falhas e concorrência | Aprovado |
| Sem reorder exceptions/PUT config | Catálogo por igualdade, tipos e captura de todas as escritas reais | Aprovado |
| Campos protegidos imutáveis | Serializers, candidata preservada, controles readonly e regressões HTTP | Aprovado |
| Pós-commit distinto de rollback | Falha pós-replace real, perda/readback, sessão bloqueada e recuperação explícita | Aprovado |
| Pacote sem ferramentas frontend | Venv externo/-I/sem checkout ou Node/npm, ambos artefatos e CLI real | Aprovado |
| Acessibilidade/lifecycle/auditoria/stdout | Componentes, monitor AdminAudit e MCP stdio instalado; limites declarados | Aprovado |
| Sem SQL/resultados/audit/MCP na UI | Igualdade integral de controles/calls, revisão de diff e separação de planos | Aprovado |
| Nenhum finding novo pendente | Revisão final sem mudança de produto; correções somente no preparo do harness | Aprovado |

## Arquivos desta entrega

- `AGENTS.md`
- `CLAUDE.md`
- `docs/ARCHITECTURE.md`
- `docs/HANDOFF.md`
- `docs/PHASE-8-SPEC.md`
- `docs/PHASE-8-STAGE-9-VALIDATION.md`
- `docs/PHASE-8-TRACEABILITY.md`
- `docs/ROADMAP.md`
- `docs/SECURITY.md`
- `docs/TEST-PLAN.md`
- `frontend/browser/batches.spec.js`
- `frontend/browser/editing.spec.js`
- `frontend/browser/harness.js`
- `frontend/browser/package.spec.js`
- `frontend/browser/reporter.js`
- `tests/browser_edit_server.py`
- `tests/installed_package_probe.py`
- `tests/installed_support.py`
- `tests/test_phase8_final_inventory.py`

Somente documentação e testes/harness. Nenhuma mudança em src/, fontes runtime
frontend, recursos gerados, schemas, persistência, MCP, dependências ou lockfile.
D-061–D-064 e as oito evidências históricas permanecem intactas.

## Encerramento

Gates, revisão de segurança/lifecycle/separação de planos e conferência dos 65
requisitos/13 critérios concluídos. A Etapa 9 encerra a Fase 8 sem alteração de
produto. D-061–D-064 e os recibos das Etapas 1–8 permanecem intactos.
O fetch final confirmou master e HEAD igual a origin/master em
`20db6f021533230d791cd910b037554c3fe03191`, 0/0 antes do commit desta entrega.
As Etapas 1–9 foram revisadas e aprovadas; a publicação final da Etapa 9 está
autorizada após amend exclusivamente editorial. Autor/committer
`w.filho <w.filho@live.com>` e trailer `Co-Authored-By: Codex <noreply@openai.com>`
permanecem preservados. O hash e a sincronização HEAD igual a origin/master,
árvore limpa e 0 ahead / 0 behind serão informados no relatório final, sem
autorreferência no documento. Na data desta medição, a Fase 9 ainda não havia
sido iniciada; sua autorização documental posterior não altera esta evidência.
