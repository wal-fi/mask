# Fase 8 — Evidência da Etapa 6

**Estado:** Etapa 6 concluída; todos os gates finais aprovados.
**Data:** 2026-09-13. **Escopo:** máquina de estados e transporte granular;
as seis telas permanecem exclusivamente de leitura.

## Checkpoint e publicação da Etapa 5

Confirmados master, HEAD `0d42f5d0d9a835177dd1c5e4a6c608161f585896`,
origin/master `7e8e39988b38438128a51fc414ecae68cdde01c1`, árvore limpa e
exatamente 1 ahead / 0 behind. Autor e committer `w.filho <w.filho@live.com>`;
trailer `Co-Authored-By: Codex <noreply@openai.com>`.

Foi publicado exatamente `0d42f5d0d9a835177dd1c5e4a6c608161f585896`, sem amend,
rebase ou alteração de arquivo. O fetch subsequente confirmou HEAD igual a
origin/master, 0/0 e árvore limpa, com autor, committer e trailer preservados.
A primeira tentativa de rede restrita falhou antes de conectar; a publicação
autorizada foi efetuada com acesso de rede adequado. A Etapa 6 permanece local.

## Estado, confirmação e recuperação

`coordinator.js` é um componente sem DOM, timer, fila ou operação implícita.
Sua construção recebe o transporte da sessão e uma chamada de leitura
autenticada; a primeira leitura também exige invocação explícita. Não é
instalado por `screen.js`, que permanece idêntico à Etapa 5.

União JSDoc fechada `Flow`: authentication, loading, reading, draft, pending,
success, conflict, busy, incompatible, unknown e uncertain. `Command` e
`Outcome` também têm contratos tipados. Valores externos são unknown até
passarem pelo interpretador e por `Number.isSafeInteger`, sem coerção,
arredondamento, any ou supressões. A próxima revision também precisa ser segura.

Cada edição mantém snapshot-base, revision-base, rascunho e comando confirmado.
Cópias profundas congeladas eliminam aliases mutáveis. O comando captura
conteúdo e revision em conjunto; a resposta usa a versão capturada antes do
fetch, não uma referência mutável do chamador. Polling durante rascunho só
registra observação separada; não troca base ou conteúdo. Durante pendência,
polling e novas mutações são recusados, sem fila. Leituras antigas ou versões
regressivas não substituem um snapshot mais recente.

| Situação | Comportamento do coordenador |
|---|---|
| load | Leitura explícita; falha bloqueia edição; retry de leitura manual |
| begin/change | Confere projeção e conserva base; nenhum request de escrita |
| confirm | Revalida o comando e admite uma única escrita pendente |
| Sucesso válido | Exige applied=true e revision seguinte; inicia releitura |
| Releitura confirmada | Conserva snapshot completo recebido; finish explícito permite outra edição |
| Sucesso com releitura falha | “Salva; visualização ainda não atualizada”; nenhuma nova edição por finish |
| Conflito | Preserva base/rascunho/comando; carrega base nova separada; review humano explícito |
| Busy | Conserva rascunho; somente outro confirm manual pode tentar novamente |
| Incompatível/out of sync | Bloqueia mutações; não corrige, repete ou desfaz automaticamente |
| Durabilidade incerta | Exige applied=true e versão coerente; relê, mantém bloqueio e não repete |
| Resultado desconhecido | Relê para observação, mas uma revision maior não prova autoria nem libera mutação |
| Cancelamento local pendente | Aborta espera e marca desconhecido; não alega cancelamento no servidor |
| Logout/401/pagehide/pageshow | Fecha sessão, limpa coordenador e invalida geração/tickets |

Novos IDs vêm somente do snapshot relido. Não há inferência por nome,
rebase/rollback automático ou coordenação entre abas. As duas sessões de teste
conservam estados independentes; a revision do servidor arbitra conflitos.

Toda reconciliação remove primeiro a base de releitura anterior. Se a nova
tentativa falhar, review/finish não podem reutilizar aquela base desatualizada.
O rascunho e seu snapshot-base original permanecem preservados. Releitura
inferior à versão informada pelo desfecho também é recusada.

## Transporte e projeção fechados

O único catálogo de operações vem dos metadados autenticados, cujo hash,
UTF-8, gramática e referências são conferidos antes de qualquer negócio.
`commands.js` cria uma cópia congelada do documento. O transporte conserva
token apenas em sua closure e descarta catálogo/modelos ao encerrar.

O plano de projeção é o modelo privado de entrada: selecionar/copiar campos
declarados e construir objetos/listas fechados. O slot ligado ao papel version
recebe somente a revision-base; fornecê-lo no rascunho é recusado. Campos extras
ou protegidos não são silenciosamente removidos: a operação inteira falha.
Não se recebe um plano de projeção arbitrário, método ou URL do chamador.
O executor de edição de candidatos/formulários continua nas etapas seguintes.

Templates contêm um único segmento de identidade. O transporte localiza o
modelo da identidade na leitura pareada do catálogo e exige o formato privado
canônico, inclusive prefixo, tamanho e alfabeto. Proíbe %, query, fragmento,
autoridade, traversal, barras, espaços e chaves estruturais perigosas. O mesmo
comando é resolvido/verificado de novo imediatamente antes do fetch.

Corpos são verificados contra o modelo completo, copiados sem getters,
protótipos customizados, símbolos, ciclos ou campos desconhecidos e limitados
a 1 MiB UTF-8. A credencial, inclusive com escapes JSON, é recusada no corpo.
O token não integra nenhuma fonte de projeção. Todo método com corpo, inclusive
DELETE, envia Content-Type application/json. Origem/destino são conferidos
antes de construir Authorization; cors/omit/error/no-store/no-referrer e o
timeout de 30 segundos permanecem. Redirects não são seguidos.

O transporte admite as dez escritas do catálogo, nunca PUT /config. `check`
permanece separado por compatibilidade da Etapa 4 e agora também verifica o
modelo de entrada antes do envio; nenhuma tela o chama. Falhas de preparação
não emitem request. Uma mutação em voo impede outra no mesmo transporte.

Sucesso e erro são validados antes de serem interpretados. A união privada de
erro fornece o discriminante; `messages` fornece categoria abstrata e texto
fixo. Detail remoto, caminhos e valores não são exibidos. Timeout, desconexão,
JSON/media type/envelope inválido ou erro interno durante escrita produzem
desconhecido. 401 limpa a sessão, sem devolver schema ou estado.

## Apresentação e separação de planos

Dois ajustes privados, sem alterar schemas HTTP:

- binding de current_revision nos envelopes de erro; ausência de campo
  opcional não substitui a validação de obrigatoriedade do modelo;
- identidades das respostas passam a reutilizar as restrições dos modelos
  autoritativos de documento/candidato, em vez de strings genéricas.

Resultado: 109 modelos deduplicados, 19 chamadas, seis vistas, oito editores e
34 controles. IDs internos de modelo mudam por deduplicação; catálogo e âncoras
são regenerados em conjunto. Nenhuma chamada nova ou exceção lexical foi criada.
Os 193 termos privados continuam ausentes dos recursos públicos.

HTML, CSS, renderer, gramática, contratos de negócio, pins e lock não mudam.
Todos os módulos Python de produto permanecem iguais, exceto `_catalog.py` e
`_anchor.py` gerados. Startup, servidor HTTP, autenticação, Host/Origin/Referer,
Fetch Metadata, CSP/headers, proxy, schemas, persistência, runtime, auditoria e
MCP não recebem mudanças. Inventários continuam 20/28 off e 24/36 on; a fixture
off e a comparação literal permanecem intactas. D-061–D-064 não são alteradas.

Não há adoção, validação pela tela, formulários funcionais, CRUD, reorder ou
edição de database/SQL nesta etapa. As operações do componente nos testes usam
transporte controlado e não chegam ao backend de escrita. Nenhum endpoint ou
store de auditoria, SQL, resultado de banco ou expansão MCP foi acrescentado.

## Testes e contraprovas

`commands.test.js`: dez operações, projeções, métodos/destinos, matriz de
revisions inválidas, overflow, identidades hostis, campos protegidos/extras,
prototype pollution/getters/símbolos/ciclos, cópias congeladas e mapeamento de
desfechos. `protocol.test.js` acrescenta quatro contraprovas de tipagem de
Flow, Command e Outcome, além das oito anteriores.

`coordinator.test.js`: transporte/coordenador reais sobre fetch controlado;
duplo clique, nenhuma fila, polling em rascunho/pendência, conflito com base
separada, busy manual, durabilidade sem repetição, resultado desconhecido sem
atribuição por revision, timeout/desconexão/500/JSON/media type, sucesso com
releitura válida/falha, cancelamento/401/sessão fechada, respostas fora de ordem,
duas sessões, snapshots imutáveis, DELETE JSON e zero fetch antes da validação.
Inclui regressão de segunda releitura fracassada após conflito já relido.

`browser/coordinator.spec.js`: oito cenários de desfecho e quatro casos de cleanup nos
três engines fixados, com os componentes reais do ESM. O harness real readonly
exige nenhum método de escrita no backend, zero AdminAudit/contador e arquivo/
snapshot inalterados, cobrindo configuração, IDs e política do runtime. Os
testes componentes não substituem os futuros fluxos reais de persistência.
As regressões de leitura, XSS, HTTP/CSRF e lifecycle continuam acumuladas.

Findings corrigidos durante a rodada: colisão de identificador na concatenação
ESM (o build ganhou node --check); modelo de identidade genérico insuficiente
para templates; anotação JSDoc de teste mal posicionada; comparação de JSON do
harness dependente da ordem das chaves; base antiga ainda revisável depois de
uma segunda releitura fracassada. Nenhum deles foi convertido em skip/xfail.
Rodadas anteriores às correções não contam como gates finais.

## Reprodução

Usar Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e
@types/node 24.0.0. Em frontend: npm ci --ignore-scripts, npm run build duas
vezes, comparar SHA-256 dos 14 outputs, npm run typecheck, npm test e npm run
inspect. O build também confere sintaxe ESM e checkJs strict/noEmit do asset.

Para browsers, MASKGW_TEST_DSN deve apontar a PostgreSQL 16 real; executar
npm run test:browser. Nesta rodada a imagem local postgres:16-alpine foi usada
com --pull never, porta aleatória apenas em 127.0.0.1 e credencial aleatória
somente em memória/ambiente. O launcher remove container e volume no finally.
Não gravar DSN, token, corpos, DOM, trace, HAR, vídeo ou screenshot.

Para Python, executar a suíte inteira sem filtros/deselects. No Windows,
launcher temporário usa threading.stack_size(64 * 1024 * 1024), chama
pytest.main(['-q', '-ra', '--junitxml=...']) numa thread, aguarda join e propaga
o exit code. Nenhuma modificação no produto/testes para contornar pilha.
Executar Ruff check, Ruff format --check e mypy --strict sobre src tests,
além de git diff --check no worktree e índice.

Construir wheel/sdist com setuptools.build_meta. Instalar cada artefato num
target temporário fora do checkout usando --no-index --no-deps
--no-build-isolation --no-compile. Executar Python -I -S com esse target,
dependências Python existentes e PATH somente do sistema; conferir origem
do import, ausência de Node/npm, quatro recursos válidos e igualdade dos bytes.
Inspecionar pacote sem frontend/tests/fixtures/sourcemaps/tipos privados.

## Limites preservados

Playwright 1.63.0 desliga BFCache e não acompanha sua restauração por goBack.
Firefox/WebKit mantêm provas de histórico/reload e eventos persisted; não há
alegação de restauração nativa nesses engines. Chromium mantém a prova nativa
adicional via CDP já aprovada, sem ampliar escopo ou alterar cache do produto.

O gate Ruff continua src tests. Os 51 diagnósticos históricos dos geradores
privados fora desse gate não são apresentados como corrigidos. Não há novo
ignore, skip ou supressão. O warning preexistente de pytest para match=""
continua sem silenciamento. Skips de plataforma serão discriminados abaixo.

Limpeza descarta referências controladas pela aplicação, sem promessa de
sobrescrever o heap ou proteger contra extensão/navegador/processo privilegiado
comprometido. Componentes controlados não provam persistência nem fecham os
gates funcionais das Etapas 7–9. Rollback continua por flag/restart; nunca
desfaz automaticamente configuração, IDs ou revision já persistidos.

## Medições finais e encerramento

Todos os gates finais passaram sobre os mesmos recursos congelados. PostgreSQL
16.15 real, sem deselect ou skip por DSN. São 77 testes Node acrescentados aos
99 anteriores (incluindo quatro contraprovas de tipagem) e 36 componentes de
navegador acrescentados às 78 regressões. Nenhum finding convertido em skip/xfail.

| Gate | Resultado medido | Tempo de processo |
|---|---|---:|
| npm ci --ignore-scripts | Instalação congelada, exit 0 | 4.69 s |
| Build 1 | Exit 0, sintaxe ESM e tipagem incluídas | 29.48 s |
| Build 2 | 14 outputs idênticos, LF | 27.70 s |
| Typecheck | strict/checkJs/noEmit, sem supressões | 5.70 s |
| Inspeção pública | 193 termos e contraprovas aprovados | 1.00 s |
| Node | 176 aprovados, zero falhas/skips | 37.01 s |
| Playwright | 114 aprovados, 38 por engine, zero falhas/skips/retries | 918.34 s |
| Python completo | 3804 coletados, 3796 aprovados, 8 skips POSIX | 536.92 s |
| Ruff check src tests | Exit 0 | 0.86 s |
| Ruff format --check src tests | 135 arquivos, exit 0 | 0.58 s |
| mypy --strict src tests | 135 arquivos, exit 0 | 2.55 s |
| Wheel/sdist | Instalação isolada e quatro recursos válidos, sem Node/npm | 40.97 s |
| git diff --check | Worktree e índice conferidos antes do commit | Sem cronometragem |

Node: 36120.441 ms internos. JUnit Python: 524.353 s; início 2026-09-13T20:48:20.679153-03:00.

Python 3.11.3; pytest 9.1.1, ruff 0.16.5, mypy 2.3.1, pydantic 2.13.5, psycopg 3.3.4, fastapi 0.141.1, uvicorn 0.52.4, mcp 2.1.1.
Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e @types/node 24.0.0; pins e lock npm v3 inalterados.

| Engine | Versão | Revisão | Casos finais |
|---|---|---|---:|
| Chromium/headless shell, mais Chromium completo no controle BFCache | 153.0.8010.12 | 1243 | 38 |
| Firefox | 155.0 | 1543 | 38 |
| WebKit | 26.6 | 2359 | 38 |

Helpers existentes: ffmpeg 1011 e winldd 1007. Nenhuma instalação/atualização de browser ou dependência nova.

Os launchers confirmaram a remoção dos containers descartáveis. A inspeção
final não encontrou containers da Etapa 6 nem processos dos seus launchers/
harness. O diretório de resultados de navegador contém somente `.last-run.json`
(45 bytes), sem screenshots, vídeos, traces ou outros artefatos de sessão.

Os oito skips são condicionais de plataforma: cinco fsync de diretório e três bits de modo POSIX. Nomes medidos no JUnit:

- `tests.test_admin_adversarial.TestLeakageNasFalhasDeEscrita.test_durability_error_depois_do_replace_nao_vaza`;
- `tests.test_admin_http_audit.TestDurabilidade.test_durability_error_publica_com_revision_after`;
- `tests.test_admin_http_writes.TestDurabilidade.test_fsync_de_diretorio_falho_publica_com_applied_true`;
- `tests.test_admin_service.TestDurability.test_real_directory_fsync_failure_is_post_commit_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_group_writable_config_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_world_writable_parent_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_reused_lock_must_be_mode_0600_on_posix`;
- `tests.test_config_filesystem.TestDurability.test_directory_fsync_failure_is_post_commit`;

## Recursos finais e pacote

Sete dos 14 outputs mudaram: apresentação privada/final, nomes de modelos, catálogo privado gerado, JS, manifesto e âncora. HTML/CSS e os demais outputs permanecem iguais à Etapa 5.

| Recurso | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| `manifest.json` | 633 | `5bdb1d87aedb962c111583a55a82a63f7a293fb5836905dba33bc9631854f37e` |
| `presentation.json` | 36687 | `9dda0f7bf0994e08f3b2340e0b3336e192aabccac9a41fde3cc17fbc258d75e2` |
| `ui.css` | 1205 | `adcdfbf6c1383fe8c767d93ecd39759435866338f73a4efcb48138142e673c17` |
| `ui.js` | 70605 | `2fd43784fd31a02cb1fae3a61d5e2525fa498d8e7f4ebf9b38a8fa08d2117403` |

| Artefato | Entradas | Bytes | SHA-256 |
|---|---:|---:|---|
| `maskgw-0.1.0-py3-none-any.whl` | 81 | 193255 | `bcddd96f607175643efa2c725df73778dc5355b3b206cf8e0ab90cf4bbac9a74` |
| `maskgw-0.1.0.tar.gz` | 104 | 162175 | `262d6ea26e5121288df72149f035d01c6ab07f14ba1946be1e5687fcd4156ec9` |

Ferramentas de pacote: setuptools 68.2.2, wheel 0.45.1, packaging 24.2. A igualdade determinística exigida é dos recursos, não de arquivos comprimidos entre horários. A instalação isolada não encerra os fluxos funcionais do pacote da Etapa 9.

## Revisão documental e arquivos

Conferidos 145 arquivos protegidos sem mudanças e as seções normativas 1–7 da especificação intactas. Estado e autorização foram atualizados para Etapa 5 publicada e Etapa 6 concluída; registros históricos continuam identificados. D-061–D-064 permanecem sem nova decisão arquitetural.

São 28 arquivos nesta entrega:

- `AGENTS.md`;
- `CLAUDE.md`;
- `docs/ARCHITECTURE.md`;
- `docs/HANDOFF.md`;
- `docs/PHASE-8-SPEC.md`;
- `docs/PHASE-8-STAGE-6-VALIDATION.md`;
- `docs/PHASE-8-TRACEABILITY.md`;
- `docs/ROADMAP.md`;
- `docs/SECURITY.md`;
- `docs/TEST-PLAN.md`;
- `frontend/README.md`;
- `frontend/browser/coordinator.spec.js`;
- `frontend/private/model-names.json`;
- `frontend/private/presentation.json`;
- `frontend/src/commands.js`;
- `frontend/src/coordinator.js`;
- `frontend/src/reader.js`;
- `frontend/src/transport.js`;
- `frontend/test/commands.test.js`;
- `frontend/test/coordinator.test.js`;
- `frontend/test/protocol.test.js`;
- `frontend/tools/build.js`;
- `frontend/tools/presentation.py`;
- `src/maskgw/admin/ui/_anchor.py`;
- `src/maskgw/admin/ui/_catalog.py`;
- `src/maskgw/admin/ui/assets/manifest.json`;
- `src/maskgw/admin/ui/assets/presentation.json`;
- `src/maskgw/admin/ui/assets/ui.js`;

## Próximo checkpoint

Um único commit local, filho de `0d42f5d0d9a835177dd1c5e4a6c608161f585896`, com autor/committer `w.filho <w.filho@live.com>` e trailer `Co-Authored-By: Codex <noreply@openai.com>`. O relatório final traz o hash completo e a confirmação de master, árvore limpa e exatamente 1 ahead / 0 behind. Não publicar Etapa 6 nem iniciar Etapa 7 antes de revisão e nova autorização.
