# Fase 8 — Evidência da Etapa 4

**Estado:** Etapa 4 concluída; gates acumulados aprovados. **Data:** 2026-09-11.
**Escopo:** fronteira HTTP condicional e transporte mínimo necessário aos testes reais.

## Checkpoint e publicação da Etapa 3

Foi confirmado `master`, HEAD `dd921d52e6a0475e3301621a547f50972d4cccbb`,
origin/master `d080886352920a663e8b0aa318761a083f54f7f7`, árvore limpa e 1 ahead /
0 behind. Foi publicado exatamente dd921d52, sem emenda. O fetch subsequente
confirmou HEAD igual a origin/master, 0/0 e árvore limpa. Autor, committer
`w.filho <w.filho@live.com>` e trailer `Co-Authored-By: Codex <noreply@openai.com>`
foram preservados. A implementação desta rodada é filha de dd921d52 e não
está autorizada a ser publicada. Nenhuma decisão D-061–D-064 foi reaberta.

## Implementação e ordem da fronteira

O composition root mantém a fonte bruta e a barreira pré-bind da Etapa 3.
Passa os recursos já validados ao HTTP, que copia o mapping em uma
`MappingProxyType`. Não lê arquivos, configuração, runtime ou PostgreSQL para
servir UI. Trocar o mapping fornecido ou os arquivos após a carga não muda os
bytes conservados nesta execução. Shutdown/join e ownership não mudaram.

Somente com UI habilitada são registradas estas quatro rotas, todas GET/HEAD:

| Caminho | Autenticação | Recurso |
|---|---|---|
| `/admin/ui` | Público canônico | HTML estático |
| `/admin/ui/assets/ui.js` | Público canônico | ESM |
| `/admin/ui/assets/ui.css` | Público canônico | CSS |
| `/admin/ui/presentation.json` | Bearer válido | Apresentação estática privada |

Inventários por igualdade: UI off **20 entradas / 28 pares método-caminho**;
UI on **24 entradas / 36 pares**. Nenhuma montagem de diretório, manifesto,
OpenAPI, docs, OPTIONS, redirect de slash ou rota auxiliar de teste no produto.

Ordem UI on: contenção e headers → Host → Origin/Referer/Fetch Metadata →
tamanho declarado → autenticação/exceção raw canônica → media type →
roteamento raw/query → handler de bytes. O limite de streaming original
permanece autoritativo quando o corpo é consumido. Reutilizam-se as primitivas
originais de bearer, tamanho, media type e serialização; UI off mantém a pilha
antiga integralmente. O servidor desabilita proxy_headers somente com UI on.

Host aceita literalmente 127.0.0.1, localhost e [::1] na porta efetiva, com
normalização limitada de caixa do hostname. Não resolve DNS nem equipara
aliases, portas ou HTTP/HTTPS. Duplicatas/autoridades ambíguas são recusadas.
Origin e Referer presentes precisam passar independentemente; null/opacos,
externos, vazios e Fetch Metadata inválido/same-site/cross-site são recusados.
Forwarded e X-Forwarded-* não influenciam a decisão.

A identificação pública usa raw_path exato. Conforme §§5.2–5.3, query não
vazia em GET/HEAD público canônico recebe 404, mesmo sem token, sem entregar
bytes; no privado recebe 401 sem bearer válido e 404 com bearer válido.
Encoding, slash, traversal e lookalikes não recebem exceção pública. O `?`
sem conteúdo é query vazia em ASGI. Não se alega recuperar delimitadores ou
traversal que o browser/parser já normalizou antes da aplicação.

## Bytes, headers, erros e isolamento

Os quatro sucessos retornam bytes e MIME exatos; HEAD mantém status/headers/
Content-Length de GET e suprime o corpo, inclusive em erro. Aplicam-se as duas
CSPs literais de §5.4: política de recursos somente no sucesso UI, política de
dados no JSON administrativo e em todos os erros. No-store, nosniff,
no-referrer, DENY, CORP/COOP same-origin e Permissions-Policy são exatos.
Nenhum CORS, cookie, Server, ETag, Last-Modified, Allow novo, compressão,
304 ou 206. Range e condicionais não criam representação parcial/cacheada.

Erros UI conservam somente error/detail fixos. Falha interna pública retorna
500; apresentação sem bearer continua 401 mesmo com recurso defeituoso.
As recusas do parser HTTP anteriores ao ASGI são verificadas separadamente:
Host duplicado real retorna 400 sem alegar headers que a aplicação não emitiu.

`Untouchable` reprova qualquer acesso a serviço/auditoria em toda a matriz,
inclusive se uma exceção for contida pelo servidor. O servidor real compara
snapshot, arquivo e chamadas do adapter; o harness de browser real compara
snapshot, arquivo e contador zero, captura auditoria/logs apenas em memória e
fecha a aplicação ao terminar. As quatro rotas UI não validam configuração,
emitem AdminAudit, incrementam contador ou acessam PostgreSQL.
O POST de controle é config:validate, sem persistência, com a auditoria
existente dessa operação preservada.

## Transporte mínimo e browsers reais

`open(token)` é uma entrada explícita, sem chamada automática ou DOM funcional.
Obtém presentation.json autenticada, limita bytes a 256 KiB, confere SHA-256
via Web Crypto, UTF-8 e gramática antes de permitir qualquer pedido de negócio.
As URLs são relativas, sem query/fragmento/encoding/traversal; origem e caminho
são conferidos antes de criar Authorization. Todo fetch usa mode cors,
credentials omit, redirect error, cache no-store e referrerPolicy no-referrer.

Somente GETs sem template e o POST abstrato check ficam disponíveis nesta
etapa. As dez escritas, templates e chamadas desconhecidas são recusados antes
da rede. Nenhum PUT /config, CRUD, sessão persistente, lifecycle de login/logout,
BFCache, polling, renderização administrativa, máquina de estados ou
reconciliação foi implementado. Respostas de negócio permanecem unknown;
validadores de DTOs consumidos pelas telas ficam nos marcos futuros.
Erros são fixos e não reproduzem corpo remoto, token ou entrada.

Os testes observaram Authorization somente na origem exata e Origin legítimo
no POST config:validate, sem preflight no fluxo legítimo. Redirects HTTP reais,
tanto relativos quanto para outra porta loopback, foram recusados sem pedido
ou bearer ao destino. Um detector positivo prova que o destino externo seria
alcançável; não confundir ausência de servidor com bloqueio de redirect.
Hash incorreto e metadado estrutural inválido (com hash coerente injetado no
harness) impedem qualquer chamada de negócio. CSRF externo com Authorization
não passa pelo preflight; POST simples sem credencial também não altera estado.
CSP bloqueia script inline com controle positivo do detector em fixture privada.
Esse ensaio não substitui XSS armazenado/rendering das etapas seguintes.

| Engine | Versão executada | Revisão Playwright |
|---|---|---|
| Chromium / headless shell | 153.0.8010.12 | 1243 |
| Firefox | 155.0 | 1543 |
| WebKit | 26.6 | 2359 |

As versões são conferidas por browser.version() no ensaio; revisões conferidas
no inventário do Playwright e instalações locais. Helpers instalados pelo pin:
ffmpeg 1011 e winldd 1007. Não há dependência nova de runtime nem mudança no lock.
Os sete cenários por engine totalizam **21 aprovados**, zero falhas/skips/retries,
em **132,72 s** do processo, com PostgreSQL 16.15 real.

Reporter serializa somente títulos estáticos/status/categorias fechadas. Token
aleatório permanece em memória/ambiente do processo privado; não entra em
argumento de comando, URL, corpo, log ou artefato. Capturas de requests/logs
não são persistidas; contextos fecham antes do relato de falha. Trace, HAR,
vídeo e screenshot estão desligados. Após a execução final, outputDir continha
somente `.last-run.json`, sem DOM, screenshot, vídeo, HAR ou trace.

## Build, tipagem e distribuição

Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e @types/node
24.0.0 preservados. Lockfile npm v3 inalterado e npm ci --ignore-scripts.
JSDoc/checkJs strict/noEmit cobre também harness, reporter e config Playwright;
o alias de importação do browser aponta para o ESM real, sem stub any.

O verificador público permite somente o fetch agora aprovado. A lista de 193
termos privados e as contraprovas de concatenação/escapes/reconstrução não foram
afrouxadas; mecanismos de HTML dinâmico e comunicação/persistência proibidos
continuam bloqueados. A inspeção examina bytes e literais decodificados.
Dois builds completos deram hashes idênticos nos 14 arquivos, com LF fixo.
Somente JS, manifesto e âncora diferem da Etapa 3. Os outros 11 arquivos gerados,
HTML/CSS/apresentação/catálogo incluídos, permaneceram byte a byte iguais.

| Gate frontend | Resultado medido |
|---|---|
| npm ci --ignore-scripts | Exit 0; 8,45 s |
| Build 1 | Exit 0; 32,64 s |
| Build 2 | Exit 0; 21,30 s; 14 arquivos idênticos |
| Typecheck strict/checkJs/noEmit | Exit 0; 4,64 s |
| Inspeção pública | Exit 0; 1,19 s; 193 entradas |
| Node | 75 aprovados, zero falhas/skips; 24,75 s do processo; 23.982,4823 ms do runner |

| Recurso interno | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| `manifest.json` | 632 | `52eeca4ff270661d6b4d73c0267ef0bfb0089df41c685a03ffcdea92356fa1b4` |
| `presentation.json` | 35212 | `0ec27cb80cb0111532e82cb2ef765810037550c33d06980b2aabc679f519a6ea` |
| `ui.css` | 232 | `c82fb0a81578900634c9e561cd7d16aaacfb9a0aec8802172ccd62c46ad786c4` |
| `ui.js` | 32893 | `5651cadff8d37019442618abc435652c9c241274456c73c027f84ac823782c51` |

Wheel e sdist foram construídos com as ferramentas já existentes (setuptools
68.2.2, wheel 0.45.1, packaging 24.2), instalados isoladamente fora do checkout,
sem rede/dependências novas. Ambos carregaram os quatro recursos sem Node/npm
no PATH e com importação comprovadamente do pacote instalado. Bytes instalados
iguais ao checkout. Nenhum frontend privado, teste, fixture, sourcemap ou tipo
privado no inventário; manifesto interno presente, sem virar recurso HTTP.
Isso repete o smoke de empacotamento de recursos; não encerra a revisão final
de pacote/fluxos da Etapa 9.

- Wheel: 81 entradas, 184.124 bytes; SHA-256
  `22f6ba03d00a5ad5b37ddaca979e4dea0d580519aebeab154a2a11cead534f3b`.
- Sdist: 104 entradas, 152.916 bytes; SHA-256
  `489694e17c2bcd919883e32377ea2fba6c3370a078de00356007f9b0657bad80`.

## Compatibilidade, ajustes de testes e limites

A fixture `tests/fixtures/phase7-ui-off.json` não foi editada. As 40 respostas
de referência são comparadas literalmente em UI off: status, corpo em bytes
e headers determinísticos, excluindo somente Date. Repr continua exato.
O teste histórico que exigia a mesma superfície com UI on foi atualizado para
a mudança explicitamente autorizada: esse modo agora usa a matriz nova. Os
hashes de app.py/server.py deixam de exigir identidade; os outros dez hashes
de primitivas HTTP/SecretProvider continuam protegidos. Nenhum finding virou
skip/xfail e nenhuma recusa foi flexibilizada para passar o gate.

A execução dos browsers encontrou ajustes necessários no harness:

- O subconjunto request.headers() do Chromium omitia Origin; a observação usa
  allHeaders(), sem imprimir headers. O POST real confirmou a origem esperada.
- Um redirect simulado por route.fulfill não era prova equivalente no WebKit;
  foi substituído por 302 real no servidor privado, sem endpoint de produto.
- O monitor inicial tratava logs operacionais INFO como falha. A captura passou
  a inspecioná-los em memória, reprovando leakage, warning inesperado e auditoria
  indevida, com controles positivos unitários.
- No CSRF do Chromium/Windows foi observado ConnectionResetError/WinError 10054
  de asyncio quando o peer encerra a conexão recusada. Somente no cenário
  adversarial explícito do Windows essa ocorrência é contada (máximo dois),
  sem dispensar a busca de secrets. Qualquer outro warning/erro continua fatal;
  o mesmo reset fora desse cenário reprova. Os controles unitários demonstram
  essas distinções. Servidor, política de origem e testes de efeitos não mudaram.

Os 21 casos completos passaram após esses ajustes. Nenhuma correção instalou
flag de browser que desabilita segurança; não houve skip, xfail ou retry.
Os limites residuais de pacote/navegador/extensão privilegiada comprometidos e
DoS local permanecem os aprovados. Não se alega proteção de sessão, BFCache,
XSS armazenado, acessibilidade, concorrência ou durabilidade de uma UI que
ainda não implementa esses fluxos.

## Gate Python e encerramento

Ambiente existente, sem atualização de dependências Python: Python 3.11.3,
pytest 9.1.1, Ruff 0.16.5, mypy 2.3.1, Pydantic 2.13.5, psycopg 3.3.4,
FastAPI 0.141.1, Uvicorn 0.52.4 e MCP 2.1.1. Versões lidas do ambiente executado.

| Gate | Resultado medido |
|---|---|
| Python completo | 3.804 coletados; 3.796 aprovados; 8 skips POSIX; zero falhas/erros/deselects/skips por DSN |
| PostgreSQL real | 16.15, imagem local postgres:16-alpine, sem pull, porta aleatória somente loopback |
| Tempo Python | 447,56 s do processo; 436,684 s no JUnit |
| Ruff check src tests | Exit 0; 0,31 s |
| Ruff format --check src tests | Exit 0; 135 arquivos; 0,36 s |
| mypy --strict src tests | Exit 0; 135 arquivos; 2,17 s |
| git diff --check | Sem erros; repetido no índice antes do commit |

O XML registra 1.325 casos em test_admin_ui_http, 90 em test_admin_ui_startup
e três em test_browser_harness. O produto cartesiano HTTP é 17 caminhos ×
oito métodos × três queries × três estados de bearer = 1.224 casos; os demais
cobrem headers, origem, precedência, falhas, imutabilidade e servidor real.
A suíte completa foi executada sem --deselect ou filtro de marcadores, com
MASKGW_TEST_DSN definido no ambiente do processo. Nenhum finding virou skip/xfail.

Como documentado nas etapas anteriores, o launcher temporário Windows executou
pytest.main(['-q', '-ra', '--junitxml=...']) numa thread com
threading.stack_size(64 * 1024 * 1024), aguardou sua conclusão e propagou o
exit code. Nenhuma alteração no produto/testes para acomodar a pilha.
O container PostgreSQL descartável e seu volume foram removidos ao fim,
com confirmação. O container independente do gate browser também foi removido.
Builds terminaram antes dos testes consumidores; nenhuma troca de recursos
durante execução. Nenhum browser ou DSN ausente foi substituído por mock.

Os oito skips são condicionais preexistentes de POSIX: cinco de fsync de
diretório e três de bits de modo. Identificados no JUnit:

- `test_admin_adversarial.TestLeakageNasFalhasDeEscrita.test_durability_error_depois_do_replace_nao_vaza`;
- `test_admin_http_audit.TestDurabilidade.test_durability_error_publica_com_revision_after`;
- `test_admin_http_writes.TestDurabilidade.test_fsync_de_diretorio_falho_publica_com_applied_true`;
- `test_admin_service.TestDurability.test_real_directory_fsync_failure_is_post_commit_on_posix`;
- `test_config_filesystem.TestValidation.test_group_writable_config_is_rejected_on_posix`;
- `test_config_filesystem.TestValidation.test_world_writable_parent_is_rejected_on_posix`;
- `test_config_filesystem.TestValidation.test_reused_lock_must_be_mode_0600_on_posix`;
- `test_config_filesystem.TestDurability.test_directory_fsync_failure_is_post_commit`;

Um warning preexistente de pytest permanece: match="" em
`test_admin_http_lifecycle.TestBootstrapComAdminHttp.test_admin_http_implica_a_secao_critica`.
Esse teste não foi modificado ou silenciado.

A revisão de segurança/lifecycle/separação conferiu: somente fronteira HTTP
condicional, recursos e transporte mínimo; nenhuma mudança em schemas,
persistência, seção crítica, runtime, auditoria ou MCP. As seções normativas
1–7 da especificação foram comparadas integralmente com dd921d52 e permaneceram
idênticas; somente estado/autorização foi atualizado. Decisões, evidências
históricas, lockfile e fixture off permanecem intactos.

Documentação de estado corrigida para Etapa 3 publicada e Etapa 4 concluída,
removendo referências correntes a ausência de HTTP/fetch e à autorização ainda
restrita à Etapa 3. O título da seção C do HANDOFF e o item residual de bind
HTTP "futuro" também foram atualizados; requisitos históricos da Fase 7 foram
preservados. A matriz identifica as provas concretas da Etapa 4 e mantém as
pendências das Etapas 5–9. Nenhuma dessas etapas foi iniciada.

### Arquivos desta entrega

- `AGENTS.md`;
- `CLAUDE.md`;
- `docs/ARCHITECTURE.md`;
- `docs/HANDOFF.md`;
- `docs/PHASE-8-SPEC.md`;
- `docs/PHASE-8-STAGE-4-VALIDATION.md`;
- `docs/PHASE-8-TRACEABILITY.md`;
- `docs/ROADMAP.md`;
- `docs/SECURITY.md`;
- `docs/TEST-PLAN.md`;
- `frontend/README.md`;
- `frontend/browser/reporter.js`;
- `frontend/browser/transport.spec.js`;
- `frontend/package.json`;
- `frontend/playwright.config.js`;
- `frontend/src/transport.js`;
- `frontend/test/transport.test.js`;
- `frontend/tools/build.js`;
- `frontend/tools/inspect.js`;
- `frontend/tsconfig.json`;
- `src/maskgw/admin/http/app.py`;
- `src/maskgw/admin/http/browser.py`;
- `src/maskgw/admin/http/server.py`;
- `src/maskgw/admin/http/ui.py`;
- `src/maskgw/admin/ui/_anchor.py`;
- `src/maskgw/admin/ui/assets/manifest.json`;
- `src/maskgw/admin/ui/assets/ui.js`;
- `src/maskgw/bootstrap/application.py`;
- `tests/browser_server.py`;
- `tests/test_admin_ui_http.py`;
- `tests/test_admin_ui_startup.py`;
- `tests/test_browser_harness.py`;

### Checkpoint de saída

Esta entrega deve ficar em um único commit local, filho de
`dd921d52e6a0475e3301621a547f50972d4cccbb`, com autor/committer
`w.filho <w.filho@live.com>` e trailer `Co-Authored-By: Codex <noreply@openai.com>`.
A confirmação do hash e do estado Git acompanha o relatório final: master,
árvore limpa, exatamente 1 ahead / 0 behind de origin/master. Não fazer push
da Etapa 4 nem iniciar a Etapa 5 sem revisão e autorização.
