# Fase 8 — Evidência de conclusão da Etapa 2

**Estado:** Etapa 2 concluída; commit local para revisão. Etapas 3–9 não iniciadas.
**Execução dos gates:** 2026-09-09 e 2026-09-10; resultados finais de 2026-09-10.

## Checkpoint e publicação autorizada

O checkpoint inicial confirmou `master`, HEAD
`aebe31d0dbaba3238e97ae3ad13bf20fdd615211`, origin/master
`27d92bd580875e9eb2abb04db102eb98af2054fe`, árvore limpa e 1 ahead / 0 behind.
A publicação enviou exatamente `aebe31d0dbaba3238e97ae3ad13bf20fdd615211`
para origin/master, sem emenda. O fetch posterior confirmou HEAD igual a
origin/master, árvore limpa e 0 ahead / 0 behind antes da implementação.
Essa é a base da Etapa 2; seu commit não está autorizado para push.

## Entrega e limites

- Stack ESM/JSDoc, checkJs/strict/noEmit, sem `any` ou supressões frontend;
  contratos privados das onze escritas existentes e união das dez escritas UI.
  `PUT /config` existe somente no contrato da API, fora do catálogo UI.
- Protocolo fechado com dois validadores independentes, referências e grafo
  limitados; catálogo privado ancorado por igualdade e fingerprint de modelos.
- Apresentação estática: 110 modelos, 19 chamadas (oito GETs, uma validação e
  dez escritas), seis vistas, oito editores e 35 controles. As descrições e
  projeções não são executadas. Nenhum dado de instalação está embutido.
- Build determinístico, quatro recursos embarcados, manifesto interno e âncora
  Python; LF fixo no Git para preservar os bytes em checkout Windows.
- Leitura Python limitada, UTF-8 estrito, integridade, catálogo e bytes imutáveis,
  sem ligação com bootstrap/startup. HTML somente shell; JS somente verificador.

Não há flag, rota, entrega HTTP, alteração de autenticação/Host/Origin/Referer,
headers, proxy, sessão, polling, formulário funcional, CRUD, transporte ou
renderização dinâmica. Schemas existentes, persistência, runtime, auditoria e
MCP permanecem sem alteração. Web Crypto no navegador e interpretação dos
metadados pertencem às etapas posteriores. Nenhum browser real é alegado como
executado nesta etapa; o gate correspondente passa a ser devido nas etapas
previstas pela especificação. As decisões D-061–D-064 continuam vigentes.

## Ferramentas e gates medidos

Node **24.20.0**, npm **11.19.0**, TypeScript **5.9.3**, Playwright **1.63.0**;
`@types/node` **24.0.0**, exclusivamente declarações para tipar também as
ferramentas/testes Node. Dependências exatas, lockfile npm **v3**, integridade e
transitivas fixadas. Sem biblioteca JavaScript de runtime. Node oficial foi
usado de diretório temporário, com SHA-256 conferido contra o distribuidor;
nenhuma versão global foi substituída e nenhum navegador foi instalado.

| Gate | Resultado medido |
|---|---|
| `npm ci --ignore-scripts` | Exit 0; 8,83 s; instalação congelada, seis pacotes |
| `npm run typecheck` | Exit 0; 4,95 s; strict/checkJs/noEmit, ferramentas/testes incluídos |
| `npm test` | 70 aprovados, zero falhas/skips; 23,88 s de processo |
| `npm run build`, primeira execução | Exit 0; 22,88 s |
| `npm run build`, segunda execução | Exit 0; 21,31 s; os mesmos 14 arquivos gerados, bytes e hashes idênticos |
| `npm run inspect` | Exit 0; 1,05 s; três recursos públicos contra 193 entradas privadas derivadas |
| Wheel e sdist | Construção, inventário, instalação isolada e carga dos quatro recursos aprovados |
| Python completo, PostgreSQL 16.15 real | 2.386 coletados: **2.378 aprovados, 8 skips POSIX, 0 falhas, 0 erros, 0 xfail** |
| Duração Python | 379,528 s no JUnit; 383,59 s do processo |
| `ruff check src tests` | Exit 0; 0,39 s; All checks passed |
| `ruff format --check src tests` | Exit 0; 0,33 s; 127 arquivos formatados |
| `mypy --strict src tests` | Exit 0; 2,08 s; 127 arquivos sem problemas |
| `git diff --check` | Sem erros no fechamento documental e no índice antes do commit |

Os 74 testes de `test_admin_ui_resources.py` estão incluídos na suíte completa;
o conjunto isolado também passou integralmente. Os 70 testes Node incluem oito
contraprovas de compilação, aceitas somente por erros de incompatibilidade de
tipos, nunca por falha de importação. Há cobertura de chaves desconhecidas,
prototype pollution (inclusive templates e caminhos), ciclos, referências,
limites inclusivos, inteiros seguros, defaults, uniões, projeções declarativas,
catálogo, UTF-8/JSON, manifesto, hashes e corrupção/ausência de recursos.
As contraprovas de vocabulário cobrem bytes, escapes, identificadores, literais
e concatenações, sem reduzir a lista derivada para satisfazer a inspeção.

A suíte Python usou `pytest.main(['-q', '-ra', '--junitxml=…'])`, sem
`--deselect`, em thread temporária com `threading.stack_size(64 * 1024 * 1024)`.
`MASKGW_TEST_DSN` foi fornecida ao processo contra PostgreSQL **16.15**, imagem
local `postgres:16-alpine`, container descartável e porta exclusivamente
`127.0.0.1`. Credenciais não foram impressas nem persistidas no repositório.
O container e seu volume foram removidos ao terminar. Não houve skip por falta
de DSN, mudança de testes existentes nem alteração de pilha no produto.

Um aviso preexistente de pytest permaneceu:
`test_admin_http_lifecycle.py::TestBootstrapComAdminHttp::test_admin_http_implica_a_secao_critica`
usa comparação com string vazia em `raises`. Não é falha nova desta etapa.

### Skips condicionais de plataforma

São cinco casos de fsync de diretório e três de bits de modo POSIX, já
condicionados ao sistema operacional. Não representam dispensa de PostgreSQL:

- `tests.test_admin_adversarial.TestLeakageNasFalhasDeEscrita::test_durability_error_depois_do_replace_nao_vaza`.
- `tests.test_admin_http_audit.TestDurabilidade::test_durability_error_publica_com_revision_after`.
- `tests.test_admin_http_writes.TestDurabilidade::test_fsync_de_diretorio_falho_publica_com_applied_true`.
- `tests.test_admin_service.TestDurability::test_real_directory_fsync_failure_is_post_commit_on_posix`.
- `tests.test_config_filesystem.TestValidation::test_group_writable_config_is_rejected_on_posix`.
- `tests.test_config_filesystem.TestValidation::test_world_writable_parent_is_rejected_on_posix`.
- `tests.test_config_filesystem.TestValidation::test_reused_lock_must_be_mode_0600_on_posix`.
- `tests.test_config_filesystem.TestDurability::test_directory_fsync_failure_is_post_commit`.

## Recursos e distribuição

| Recurso | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| `manifest.json` | 632 | `bf39e3bd400a801a549e9279b30fdb1e2b842b4beeb9276d74e05a9962676235` |
| `presentation.json` | 35212 | `0ec27cb80cb0111532e82cb2ef765810037550c33d06980b2aabc679f519a6ea` |
| `ui.css` | 232 | `c82fb0a81578900634c9e561cd7d16aaacfb9a0aec8802172ccd62c46ad786c4` |
| `ui.js` | 29178 | `fe73926f83926b9c92226eb72bff49c69e5d649c65b3f8accbf0e99c04b4785a` |

`manifest.json` é interno: não constitui quinto recurso HTTP. A apresentação
é privada; somente HTML/JS/CSS passam pela inspeção de vocabulário público.
A identidade dos 14 arquivos compara sete arquivos privados de build, cinco
arquivos da pasta assets e os dois módulos privados de âncora/catálogo.
Não se alega determinismo binário de archives wheel/sdist, que incluem metadata
de empacotamento; o determinismo exigido e medido é dos recursos gerados.

| Pacote | Artefato | Entradas | Bytes | SHA-256 da execução |
|---|---|---:|---:|---|
| wheel | `maskgw-0.1.0-py3-none-any.whl` | 78 | 178298 | `250ff3c4850ea97c7f100c46776d94e1093e86d09cfcfcd868808967ef9a7d1b` |
| sdist | `maskgw-0.1.0.tar.gz` | 101 | 148031 | `f89a831657068504c1f7c1dafcba1720f6210a9dc477ab66ccb4f3f467048144` |

Ambos contêm exatamente os cinco arquivos internos de assets esperados,
sem frontend privado, ferramentas, testes/fixtures, sourcemaps ou `.d.ts`.
O sdist também foi verificado contra links simbólicos. Cada distribuição foi
instalada com `--no-index --no-deps --no-build-isolation --no-compile --target`
em diretório temporário distinto. A carga foi feita fora do checkout,
com Python `-I -S`, origem do módulo conferida sob o destino instalado e
Node/npm ausentes do PATH. As dependências Python existentes foram reutilizadas
explicitamente, sem carregar o checkout editável. Os quatro recursos passaram
por `load_resources()` nos dois destinos; todos os bytes instalados foram
comparados por igualdade com os arquivos finais de origem. Construção/instalação não executa npm.

O ambiente original não possuía `bdist_wheel` e seu setuptools era inferior ao
mínimo declarado. O gate usou ambiente temporário com **setuptools 68.2.2,
wheel 0.45.1 e packaging 24.2**, preservando a `.venv` do produto. O roteiro de
verificação também foi corrigido para usar o destino explícito de build e um
PATH mínimo no Windows; essas falhas do roteiro não foram convertidas em skips.
Permanecem avisos de empacotamento sobre README ausente na raiz e padrões
excluídos sem correspondência, sem falta de recurso na distribuição.

Durante desenvolvimento, uma execução isolada coincidiu com regeneração de
assets/âncoras e detectou o conjunto transitório inconsistente. Repetida após
congelar os recursos, passou 74/74; a suíte completa acima foi executada com
os recursos LF finais. O último ajuste de tipagem só mudou declarações privadas:
os builds posteriores comprovaram que todos os demais 13 arquivos gerados,
inclusive recursos e âncoras validados por Python/empacotamento, ficaram idênticos.
Build e testes consumidores devem permanecer sequenciais.

A conferência final contra os bytes do índice Git detectou CRLF gerado no
Windows, normalizado pelo checkout LF. Os geradores passaram a gravar LF
explicitamente; a regressão Node verifica todos os 14 resultados e o núcleo JS.
Os gates finais foram repetidos após essa correção, incluindo igualdade dos
hashes no índice, para impedir que o commit alterasse bytes do manifesto.

As declarações finais distinguem sucesso de durabilidade incerta: o desfecho
incerto exige o envelope `CONFIG_DURABILITY_ERROR` com `applied=true`, e não
aceita resposta de sucesso nem pode ser classificado como simples rejeição.
Fixtures positivas e contraprovas de tipagem fixam essa separação. Não há
máquina de estados executável nesta etapa.

## Revisão de segurança, documentação e encerramento

A revisão confirmou a separação entre bytes públicos e catálogo privado,
catálogo exato sem PUT integral, ausência de transporte/armazenamento de token,
nenhum conteúdo administrativo executável, nenhuma ligação ao servidor e nenhum
finding convertido em skip/xfail. Corrupção falha com mensagem fixa sem cadeia
de exceção. As âncoras detectam corrupção/incompatibilidade; não prometem proteger
contra substituição integral de um pacote comprometido.

A matriz `PHASE-8-TRACEABILITY.md` registra os componentes/testes entregues e
preserva explicitamente requisitos ainda pendentes das Etapas 3–9. Foram
atualizados AGENTS, CLAUDE, HANDOFF, ROADMAP, ARCHITECTURE, SECURITY e TEST-PLAN.
O corpo normativo da especificação foi preservado; somente estado e registro
de autorização mudaram. No índice de leitura do HANDOFF, a referência antiga
D-001–D-057 foi atualizada para D-001–D-064 e a descrição do roadmap deixou de
limitar o histórico a seis fases. Evidências históricas continuam históricas.

O fechamento exige um único commit local filho de
`aebe31d0dbaba3238e97ae3ad13bf20fdd615211`, autor e committer
`w.filho <w.filho@live.com>`, trailer
`Co-Authored-By: Codex <noreply@openai.com>`, master limpo e exatamente
1 ahead / 0 behind de origin/master. Não publicar esse commit nem iniciar
Etapa 3 antes de nova revisão/autorização.
