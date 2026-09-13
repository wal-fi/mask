# Fase 8 — Evidência da Etapa 5

**Estado:** Etapa 5 concluída; gates acumulados finais aprovados.
**Datas:** implementação/primeiras medições em 2026-09-12; encerramento em 2026-09-13. **Escopo:** sessão local em memória e seis vistas readonly.

## Checkpoint e publicação da Etapa 4

Confirmados master, HEAD `7e8e39988b38438128a51fc414ecae68cdde01c1`,
origin/master `dd921d52e6a0475e3301621a547f50972d4cccbb`, árvore limpa e 1 ahead /
0 behind. Autor e committer `w.filho <w.filho@live.com>`, trailer
`Co-Authored-By: Codex <noreply@openai.com>`. Foi publicado exatamente 7e8e399,
sem amend/rebase/alteração, seguido de fetch e confirmação HEAD=origin/master,
0/0 e árvore limpa. A Etapa 5 é filha desse commit e não será publicada nesta
rodada. D-061–D-064 continuam aprovadas sem nova decisão ou reabertura.

## Sessão, transporte e descarte

A entrada pública instala somente um formulário sem chamada administrativa.
O campo é password, sem autocomplete solicitado/spellcheck; fica vazio
imediatamente ao enviar, inclusive antes de terminar a carga de metadados.
O estado de apresentação não recebe token: a credencial permanece na closure
do transporte e entra somente no Authorization do destino relativo validado.
URL, histórico, atributos, globals, logs, erros e stores não recebem a credencial.
Não há cookie, Web Storage, IndexedDB, Cache API, SW, BroadcastChannel ou
postMessage. Os dois últimos mecanismos e Cache API têm contraprovas lexicais.

`open` conserva a verificação Web Crypto/hash/UTF-8/gramática da Etapa 4 e
acrescenta encerramento, sinal de cancelamento e callback de expiração. O
transporte limpa token/mapa de chamadas/metadados e aborta requests ao fechar.
Sair, 401, pagehide/pageshow e reload retornam ao login. A limpeza apaga o
conteúdo dos descendentes antes de removê-los, descarta os DTOs e invalida a
geração. Respostas antigas, inclusive fetch simulado que ignora abort, não
restauram estado ou credencial. Timers param, e cada navegação invalida a leitura
anterior. Timeout de leitura de 30 s termina em erro sanitizado, sem retry.

O POST abstrato check da Etapa 4 permanece por compatibilidade do seu gate,
mas `screen.js` invoca exclusivamente read. As dez escritas, templates e
chamadas desconhecidas continuam recusados antes de fetch. Não há validação
de proposta, adoção, escrita, rollback, CRUD ou reconciliação pela interface.
Erros não reproduzem corpo remoto. DTO que reflete a credencial, incluindo
aspas e barras que JSON escapa, é recusado antes de retornar ao estado.

## Leitura, contrato e apresentação

`reader.js` interpreta apenas os modelos e bindings autenticados. Valida
objetos fechados, obrigatoriedade/nullability, tipos, enums, limites, prefixos,
alfabetos, inteiros seguros, duplicatas de identidade e posição nas listas.
Revisões negativas, booleanas, fracionárias/inseguras ou divergentes dentro do
envelope são recusadas; adoção e revision são conferidas conjuntamente.
Nenhum campo é inventado para completar resposta. Dados permanecem unknown
até a validação; grafo/profundidade/chaves estruturais perigosas continuam
fechados. Não há cast/supressão de tipagem para aceitar DTO.

Seis vistas são derivadas da apresentação privada: Visão geral, Configuração,
Regras, Exceções, Banco e Política SQL. Há apenas uma seleção/snapshot corrente
em memória. Configuração mostra documento declarado; Banco mostra seus limites;
Política SQL identifica proteções efetivas. Não se compõem respostas de
endpoints distintos. Labels foram localizados e as projeções de leitura
ajustadas no autor privado, sem mudar gramática, modelos, chamadas ou contratos.
O catálogo conserva 19 chamadas, oito editores e seis vistas; há 110 modelos e
34 controles efetivamente presentes. Os editores/ações não são executados.

Status usa somente os campos do endpoint: revision/adoção, runtime, contadores
e secrets configured/missing. “Respondendo” indica leitura administrativa,
não saúde PostgreSQL ou cliente MCP conectado. Mostra última leitura; distingue
carregando, vazio, respondendo, desatualizado, indisponível e autenticação.
Status é solicitado a cada 15 s após a resposta anterior, somente visível,
sem sobreposição e suspenso após falha. Retry é explícito. Mudança de revision
no status descarta a leitura incompatível em vez de combiná-la. Erro da API
pode preservar a última leitura, claramente desatualizada; não atualiza seu
horário. PostgreSQL desconectado após startup não impede necessariamente GETs
administrativos; a falha de startup sem PostgreSQL permanece a anterior.

O renderer usa criação explícita, textContent e elementos semânticos (form,
label, password, botões, nav, headings, section, dl/ol). Conteúdo administrativo
fica somente em texto transitório, nunca em seletor/HTML/atributo executável.
Foco segue heading ao navegar e retorna ao token ao sair/expirar; status usa
aria-live. CSS local, system font, quebra de texto longo, viewport de 320 px, zoom de conteúdo
CSS de 200% injetado somente pelo harness,
focus visível e reduced motion, sem recurso externo ou biblioteca de runtime.
IDs, revision e allowed_pg_functions são somente leitura. SQL, resultados,
auditoria consultável e MCP não têm controle ou endpoint novo.

## Provas de navegador e limites do BFCache

Playwright 1.63.0 padrão, sem pacote experimental de Component Testing.
`reading.spec.js` usa o composition root/AdminConfigService reais e PostgreSQL
real; interceptação privada controla falhas, atraso, DTOs e relógio/visibilidade.
O harness persiste seis payloads hostis em match e parâmetros antes do startup;
outra sessão verifica texto preservado e ausência de execução/rede externa.
Cada campo textual dos DTOs é adulterado isoladamente: modelos permissivos
renderizam texto e modelos restritos recusam a resposta inteira antes do estado.
Os controles positivos acumulados provam que detectores de execução e rede
funcionam. Erro refletido com credencial não chega à mensagem da interface.

O modo readonly do harness reprova qualquer método fora de GET/HEAD, qualquer
AdminAudit e qualquer mudança de arquivo/snapshot/contador administrativo.
A desconexão PostgreSQL termina backends reais apenas no container descartável;
o encerramento da API usa canal privado stdin. Nenhuma dessas ações é rota,
flag ou funcionalidade do produto. O servidor e o runtime fecham ao final.

Os três engines executam pagehide/pageshow com persisted=true sobre sessão
real, leituras atrasadas, logout, 401, metadata pendente e reload/histórico.
A prova adicional de `lifecycle.spec.js` usa uma página-fixture local dos mesmos
bytes, elegível a cache. No Chromium completo do mesmo pin, remove-se somente
--disable-back-forward-cache e observa-se retorno nativo por CDP: persisted=true,
main exatamente com o texto público de login, campo vazio e nenhuma navegação
administrativa. A aplicação não recebe flag de teste e continua com no-store.

**Limitação explícita:** os tipos locais de Playwright 1.63.0, documentação de
Page.goBack em playwright-core/types/types.d.ts, informam que BFCache é desligado
nos engines e que a navegação automatizada não acompanha sua restauração.
As primeiras tentativas por goBack confirmaram esse limite. Não foram convertidas
em skip/xfail: a prova nativa Chromium usa CDP; Firefox/WebKit mantêm provas de
histórico/reload e do contrato de eventos persisted, sem alegar restauração
nativa nesses dois engines. Essa diferença não muda o requisito de cleanup.

Reporter emite apenas títulos estáticos, status, categorias fechadas e números
de linha dos testes. Não serializa exceções, corpos, headers ou DOM. Capturas
ficam em memória; contextos fecham antes de reportar falha. Trace/HAR/vídeo/
screenshot permanecem desligados, inclusive nos componentes e controles.

## Revisão de segurança e escopo

Comparação com 7e8e399 confirmou as seções normativas 1–7 da especificação
idênticas e 84 arquivos protegidos iguais, incluindo módulos Python de produto
(exceto âncora gerada), decisões, pins/lock, gramática, contratos, catálogo,
vocabulário e fixture off. Nenhuma mudança em startup, rotas/headers, auth,
Host/Origin/Referer/Fetch Metadata, proxy, schemas, persistência, runtime,
auditoria ou MCP. Inventários seguem 20/28 off e 24/36 on; a matriz acumulada
continua exigindo igualdade, e a fixture off compara 40 respostas literalmente.

A revisão corrigiu transbordamento de h1 a 200% de zoom e proteção contra
credencial refletida com escapes JSON. No teste de polling, uma retenção de
45 s atravessava o timeout de 30 s; a prova de não sobreposição agora mantém
resposta por 20 s (mais que um período de polling), e falha/suspensão/retry são
ensaiados separadamente. Nada foi dispensado por DSN, browser, skip ou xfail.

O gate Ruff acumulado continua `ruff check src tests`. Uma exploração adicional
com `ruff check .` encontrou 51 diagnósticos preexistentes nos três geradores
Python privados de build, fora desse gate: catalog 1, generate 21, presentation
29. Comparação pelo stdin contra HEAD confirmou as mesmas contagens antes e
depois; novos avisos locais de formatação/comparação foram corrigidos sem mudar
o resultado gerado. Não há novo ignore, supressão ou alteração da política de
lint. Essa dívida histórica não é apresentada como um `ruff check .` verde.

Riscos residuais aprovados continuam: extensão/navegador/processo/pacote
privilegiado comprometido e DoS local. Limpeza descarta referências controladas
pela aplicação, sem promessa de sobrescrita física do heap gerenciado ou de
controle sobre extensões/password managers. Os testes verificam semântica,
labels e foco; não alegam ensaio humano com hardware de tecnologia assistiva.
Etapas 6–9, escrita, rascunhos, reconciliação e revisão final da fase não foram
iniciadas. Nenhum finding antigo é encerrado por esta entrega.

Uma rodada final foi interrompida antes de concluir navegadores/Python. Seus
resultados parciais não contam como gate concluído. Na retomada foram
identificados e removidos os dois containers/volumes descartáveis criados
nessa rodada, sem processos de teste ainda ativos, e ambos os gates foram
reexecutados integralmente. A instalação final de wheel/sdist já concluída
foi conferida contra os mesmos bytes; não foi inferida da execução parcial.

## Reprodução dos gates

Usar os pins e ambiente já existentes. Na pasta frontend: `npm ci --ignore-scripts`,
dois `npm run build` completos, comparação SHA-256 dos 14 outputs, `npm run typecheck`,
`npm test` e `npm run inspect`. O build verifica também o ESM final com checkJs
strict/noEmit, sem skipLibCheck. A lista de 193 termos e as contraprovas de
encoding/concatenação permanecem fechadas; nenhuma exceção lexical nova.

Com MASKGW_TEST_DSN apontando para PostgreSQL 16 real, executar `npm run test:browser`.
O gate desta rodada cria container postgres:16-alpine da imagem local, sem pull,
porta aleatória apenas em loopback e credencial aleatória só em memória/ambiente.
Não registrar DSN. Executar Python completo na raiz, sem filtros/deselects; no
Windows, o launcher temporário chama pytest.main(['-q','-ra','--junitxml=...'])
em thread com threading.stack_size(64 * 1024 * 1024), aguarda join e propaga o
exit code. Isso não muda produto ou testes. Depois: Ruff check/format --check e
mypy --strict sobre src tests, além de git diff --check no worktree e no índice.

Buildar wheel/sdist com setuptools.build_meta, instalar cada artefato com
--no-index --no-deps --no-build-isolation --no-compile em target temporário
fora do checkout. Invocar Python -I -S desse diretório, apontando somente target
e dependências Python existentes, PATH reduzido ao sistema. Conferir origem
do import, ausência de Node/npm, quatro recursos carregados e bytes instalados
iguais aos finais; inspecionar inventários sem frontend/tests/docs/fixtures/map/d.ts.
Os recursos devem ficar congelados durante todos os testes consumidores.

## Medições finais

Ambiente medido: Python 3.11.3, pytest 9.1.1, ruff 0.16.5, mypy 2.3.1, pydantic 2.13.5, psycopg 3.3.4, fastapi 0.141.1, uvicorn 0.52.4, mcp 2.1.1.
Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e
@types/node 24.0.0; lock npm v3 inalterado. Nenhuma dependência nova.

| Engine | Versão | Revisão | Resultado final |
|---|---|---|---|
| Chromium/headless shell, mais Chromium completo no controle BFCache | 153.0.8010.12 | 1243 | 26 aprovados |
| Firefox | 155.0 | 1543 | 26 aprovados |
| WebKit | 26.6 | 2359 | 26 aprovados |

Helpers existentes: ffmpeg 1011 e winldd 1007. browser.version() é conferido
a cada cenário. São 57 casos novos de leitura/componentes e 21 regressões
da Etapa 4; zero falhas, skips, retries ou resultados esperados de falha.
O outputDir final contém somente .last-run.json (45 bytes), sem artefatos
de DOM, trace, screenshot, vídeo ou HAR. Processos de browser/harness e
containers/volumes descartáveis foram conferidos encerrados/removidos.

| Gate | Resultado medido | Tempo do processo |
|---|---|---|
| npm ci --ignore-scripts | Exit 0; instalação congelada | 3,78 s |
| Build 1 | Exit 0 | 26,34 s |
| Build 2 | 14 outputs idênticos; LF | 20,22 s |
| Typecheck | strict/checkJs/noEmit aprovado | 4,97 s |
| Inspeção pública | 193 termos; nenhuma exceção nova | 1,06 s |
| Node | 99 aprovados; zero falhas/skips | 23,69 s |
| Componentes/E2E reais | 78 aprovados; PostgreSQL 16.15 | 720,19 s |
| Python completo | 3.804 coletados, 3.796 aprovados, 8 skips POSIX | 544,12 s |
| Ruff check src tests | Exit 0; escopo de 135 arquivos Python | 1,33 s |
| Ruff format --check src tests | Exit 0; escopo de 135 arquivos Python | 1,36 s |
| mypy --strict src tests | Exit 0; escopo de 135 arquivos Python | 3,34 s |
| Wheel + sdist | Build, inventário e instalação isolada aprovados | 19,78 s |
| git diff --check | Sem erros; worktree e índice conferidos antes do commit | Verificação sem cronometragem |

Tempo interno do runner Node: **22.924,9567 ms**; JUnit Python: **533,395 s**.
Python final iniciou em 2026-09-13T09:08:52.530737-03:00. Sem filtros,
deselects, erros ou skips por DSN. O warning preexistente de pytest para
match="" em test_admin_http_implica_a_secao_critica permanece sem silenciamento.

Os oito skips são exclusivamente condicionais POSIX: cinco fsync de diretório
e três bits de modo; nenhum finding novo foi convertido em skip/xfail:

- `tests.test_admin_adversarial.TestLeakageNasFalhasDeEscrita.test_durability_error_depois_do_replace_nao_vaza`;
- `tests.test_admin_http_audit.TestDurabilidade.test_durability_error_publica_com_revision_after`;
- `tests.test_admin_http_writes.TestDurabilidade.test_fsync_de_diretorio_falho_publica_com_applied_true`;
- `tests.test_admin_service.TestDurability.test_real_directory_fsync_failure_is_post_commit_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_group_writable_config_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_world_writable_parent_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_reused_lock_must_be_mode_0600_on_posix`;
- `tests.test_config_filesystem.TestDurability.test_directory_fsync_failure_is_post_commit`;

## Inventários e hashes finais

Dois builds idênticos nos 14 outputs. Somente seis diferem da Etapa 4:
JS, CSS, apresentação privada/final, manifesto e âncora. Os demais oito,
incluindo HTML, contratos, gramática, vocabulário e catálogo, não mudam.

| Recurso interno | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| `manifest.json` | 633 | `694929c00ac57c9e4cb5c05da89fdac5b22b516ef154dd741f004e8fa1cb97f5` |
| `presentation.json` | 35378 | `8be0754cb372819e1593473a50b73d699e28a19f0644a9cea94dc170b9149c2c` |
| `ui.css` | 1205 | `adcdfbf6c1383fe8c767d93ecd39759435866338f73a4efcb48138142e673c17` |
| `ui.js` | 50511 | `8ee63f8c50f56db1f50df8e6dd1e04870d53abf676b1ea5c32357c5795d2941d` |

Wheel/sdist foram construídos com setuptools 68.2.2, wheel 0.45.1 e packaging
24.2 existentes. Ambos foram instalados fora do checkout, sem Node/npm no PATH,
com origem do import comprovada, quatro recursos válidos e bytes iguais aos
finais. Nenhum frontend privado, teste, fixture, sourcemap ou declaração no
pacote. Manifesto interno não se torna rota. Esse smoke não encerra o gate
final de fluxos do pacote da Etapa 9. A igualdade determinística exigida é dos
14 outputs; não se alega identidade de arquivos comprimidos entre horários.

| Artefato | Entradas | Bytes | SHA-256 |
|---|---:|---:|---|
| `maskgw-0.1.0-py3-none-any.whl` | 81 | 188999 | `d5487a1b82c9d2a66f33db395b80f4ab51c762d0ecb5f5d86f10112c1df54adb` |
| `maskgw-0.1.0.tar.gz` | 104 | 157819 | `809582843ff4b641ecec2d787b0f1e85f26c0b3ed99a427af872c14dd5836ebe` |

## Documentação e arquivos da entrega

Estado/autorização foram atualizados para Etapa 4 publicada e Etapa 5 concluída.
As afirmações correntes de ausência de sessão/telas/polling foram substituídas
pelo comportamento entregue; evidências anteriores e requisitos históricos
corretos permanecem. A rastreabilidade liga componentes, gates e limitações
às pendências explícitas das Etapas 6–9; D-061–D-064 não mudam.

São **32 arquivos**:

- `AGENTS.md`;
- `CLAUDE.md`;
- `docs/ARCHITECTURE.md`;
- `docs/HANDOFF.md`;
- `docs/PHASE-8-SPEC.md`;
- `docs/PHASE-8-STAGE-5-VALIDATION.md`;
- `docs/PHASE-8-TRACEABILITY.md`;
- `docs/ROADMAP.md`;
- `docs/SECURITY.md`;
- `docs/TEST-PLAN.md`;
- `frontend/README.md`;
- `frontend/browser/harness.js`;
- `frontend/browser/lifecycle.spec.js`;
- `frontend/browser/reading.spec.js`;
- `frontend/browser/reporter.js`;
- `frontend/browser/transport.spec.js`;
- `frontend/private/presentation.json`;
- `frontend/src/reader.js`;
- `frontend/src/screen.js`;
- `frontend/src/transport.js`;
- `frontend/test/reader.test.js`;
- `frontend/test/samples.js`;
- `frontend/test/transport.test.js`;
- `frontend/tools/build.js`;
- `frontend/tools/inspect.js`;
- `frontend/tools/presentation.py`;
- `src/maskgw/admin/ui/_anchor.py`;
- `src/maskgw/admin/ui/assets/manifest.json`;
- `src/maskgw/admin/ui/assets/presentation.json`;
- `src/maskgw/admin/ui/assets/ui.css`;
- `src/maskgw/admin/ui/assets/ui.js`;
- `tests/browser_server.py`;

## Encerramento e próximo checkpoint

Um único commit local da Etapa 5, filho de
`7e8e39988b38438128a51fc414ecae68cdde01c1`, com autor/committer
`w.filho <w.filho@live.com>` e trailer `Co-Authored-By: Codex <noreply@openai.com>`.
Hash e confirmação de master, árvore limpa, exatamente 1 ahead / 0 behind
acompanham o relatório final. Não publicar esse commit nem iniciar a Etapa 6
sem revisão e autorização. Rollback continua pela flag e restart, sem desfazer
configuração/IDs/revision; a entrega readonly não efetua essas mutações.
