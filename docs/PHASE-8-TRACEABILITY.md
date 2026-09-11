# Fase 8 — matriz de rastreabilidade normativa

**Estado:** aprovada; Etapas 1 e 2 publicadas; Etapa 3 publicada; Etapa 4 concluída. **Atualização:** 2026-09-11.
**Fonte normativa integral:** [PHASE-8-SPEC.md](PHASE-8-SPEC.md), aprovada
integralmente, com decisões [D-061 a D-064](DECISIONS.md#d-061--ui-administrativa-embarcada-opt-in-e-na-mesma-origem).

Esta matriz é um índice verificável, não uma versão reduzida da especificação.
Cada linha cobre **todos** os requisitos, listas, limites e contraprovas das
subseções indicadas, inclusive quando a descrição abaixo não os repete.
O texto integral prevalece. O mapeamento é muitos-para-muitos: um gate comum
não dispensa os testes específicos. A fundação da Etapa 2 está implementada nos limites do quadro de entrega abaixo;
requisitos que atravessam etapas continuam parcialmente pendentes. Nenhum gate
de navegador/HTTP ou fluxo funcional é inferido desses testes de fundação.

A Etapa 4 foi autorizada após revisão e publicação da Etapa 3. As Etapas 5–9
continuam sem autorização. A tabela normativa mantém os componentes previstos;
o quadro de entrega identifica quais já existem, sem antecipar APIs.
As seções 1–2 e 8 também fundamentam D-061–D-064; a seção 7 fixa ordem, aceite
e rollback. Evidências: [Etapa 1, histórica](PHASE-8-STAGE-1-VALIDATION.md) e
[Etapa 2, histórica](PHASE-8-STAGE-2-VALIDATION.md) e
[Etapa 3, histórica](PHASE-8-STAGE-3-VALIDATION.md). Rodada atual:
[Etapa 4](PHASE-8-STAGE-4-VALIDATION.md).

## Gates acumulados

| Gate | Evidência exigida | Marco |
|---|---|---|
| G-PY | Suíte Python inteira, sem deselect, PostgreSQL 16 real e nenhum skip por DSN; Ruff, format check, mypy strict e diff check; skips de plataforma discriminados | Etapa 1 e todas as seguintes |
| G-TYPE | Configuração e versões exatas de §6.1; checkJs strict sem erros, contratos e estados sem any/escapes proibidos | Desde a Etapa 2 |
| G-UNIT | Testes Node e Python de gramática, catálogo, bytes, manifesto, limites e contraprovas acumulados | Desde a Etapa 2 |
| G-HTTP | Matriz HTTP completa de §§5.1–5.4, requisições ASGI brutas e servidor real; UI ligada/desligada | Etapas 3–4; regressão nas seguintes |
| G-COMP | Componentes e estados com Playwright padrão, controles semânticos e DOM seguro; sem depender apenas de snapshots | Conforme componentes surgirem, Etapas 5–8 |
| G-E2E | Chromium, Firefox e WebKit reais nas versões fixadas, PostgreSQL real e cenários de §6.6; nenhum substituto por mock para a prova real | Fetch real na Etapa 4; fluxos acumulados nas Etapas 5–9 |
| G-SEC | Contraprovas de §6.7, leakage, CSRF, XSS, autenticação, rotas, headers, lifecycle, concorrência e invariantes da Fase 7 | Acumulado por componente; completo na Etapa 9 |
| G-PKG | Builds determinísticos, wheel e sdist instalados fora do checkout, recursos embarcados íntegros e execução sem toolchain frontend | Build na Etapa 2; pacote instalado e fechamento na Etapa 9 |

Cada etapa termina com a suíte acumulada verde. Gates de frontend não são
executáveis na Etapa 1, que proíbe criar sua infraestrutura ou instalar suas
dependências. Isso delimita a entrega documental, não autoriza omitir os gates
quando devidos. Ausência de browser/DSN ou finding não vira skip/xfail.

## Requisitos, componentes e testes

| ID | Fonte e requisito normativo | Etapas 2–9 | Componente previsto | Testes/gates correspondentes |
|---|---|---|---|---|
| F8-001 | §§1.1–1.2, 2: UI local embarcada no mesmo processo/origem; custos e alternativas explicitamente aprovados | 2–4, 9 | Pacote Python, composition root, HTTP UI | G-PKG/G-HTTP; nenhum servidor auxiliar ou origem configurável |
| F8-002 | §1.3: flag bruta somente valor exato 1; dependência da Admin API, valores ausentes/inválidos e repr conforme contrato | 3, 9 | Configuração de startup | G-UNIT/G-HTTP; matriz de valores brutos e combinações admin/UI, sem normalização permissiva |
| F8-003 | §1.4: recursos válidos antes de lock, conexão, bind e MCP; falha fecha startup | 3, 9 | Bootstrap e carregador de recursos | Contadores e ordem de efeitos; falhas injetadas sem porta/thread/runtime/lock indevido; G-PY/G-SEC |
| F8-004 | §1.4: lifecycle integrado, shutdown e ownership preservados | 3, 9 | Composition root e servidor | G-PY/G-HTTP; regressões de startup/shutdown e stdout exclusivo do MCP |
| F8-005 | §1.5: UI desligada preserva status, corpos, headers determinísticos e representações da Fase 7 | 3–4, 9 | Fronteira HTTP condicional | Comparação byte a byte, Date controlado/separado, flag desligada sem recursos carregados; G-HTTP |
| F8-006 | §2: sem CORS/porta separada/webview como atalho para a arquitetura aprovada | 2–4, 9 | Build e topologia | Revisão de dependências, processos e requests; G-PKG/G-SEC |
| F8-007 | §3.1: escopo fechado; nenhuma execução SQL, resultado, DBA, auditoria consultável/store/endpoint, MCP, bulk ou substituição completa | 2, 5–9 | Catálogo, páginas e transporte | Igualdade do catálogo, controles e requests; ausência de PUT /config, endpoints e stores proibidos; G-UNIT/G-SEC |
| F8-008 | §3.2: páginas, navegação em memória e estados da especificação, sem novas URLs de navegação | 2, 5, 9 | Apresentação privada e navegação | G-COMP/G-E2E; sete páginas incluindo entrada e seis vistas, seleção/retorno e reload |
| F8-009 | §3.3: campos reais de status, polling de 15 s somente visível e interrupção após falha | 5, 9 | Leitura de status e relógio | G-COMP/G-E2E; visibilidade, falha, retomada explícita, sem inventar saúde PostgreSQL ou cliente MCP conectado |
| F8-010 | §3.4: snapshot de configuração, política declarada/efetiva e proteção readonly, sem YAML bruto | 2, 5, 9 | DTOs e vista de configuração | Fixtures divergentes declarada/efetiva, revisão única e proteção; G-TYPE/G-COMP/G-E2E |
| F8-011 | §3.5: CRUD granular de regras, campos e defaults corretos, reorder específico | 2, 7–9 | Editor de regras e chamadas | GET/POST/PUT/DELETE granulares, contains e case-insensitive, IDs estáveis e reorder separado; G-E2E/G-PY |
| F8-012 | §3.6: CRUD de exceptions, exact por default e nenhuma reordenação | 2, 7–9 | Editor de exceptions | G-COMP/G-E2E; comparação de corpo, ausência de reorder, posição e semântica preservadas |
| F8-013 | §3.7: oito transformers, parâmetros/limites exatos e dependências; sem regex/preview de negócio em JS | 2, 7, 9 | Modelos privados e controles | G-TYPE/G-UNIT/G-COMP; todos os transformers, limites, campos condicionais e random length 0 válido quando permitido |
| F8-014 | §3.8: database apenas campos/intervalos inteiros aprovados, sem DSN | 2, 8–9 | Editor database | Limites 100–600000 e 1–1000000, tipos inválidos, payload dedicado; G-TYPE/G-E2E |
| F8-015 | §3.8: SQL policy somente aditiva, proteções efetivas preservadas | 2, 8–9 | Editor de adições SQL | G-COMP/G-E2E; adicionar, duplicatas/recusas e ausência de remoção, allowed_pg_functions readonly |
| F8-016 | §3.9: config:validate sem expected_revision, raiz candidata e projeção de novos itens sem IDs/revision | 2, 6–7, 9 | Projeção privada e validação | G-TYPE/G-UNIT/G-E2E/G-PY; contrato raiz, proteção preservada e nenhum efeito em disco/runtime/revision |
| F8-017 | §3.10: adoção legada apenas expected_revision 0 e confirmação explícita, checkbox inicialmente falso | 6–7, 9 | Diálogo de adoção | Cancelar/recusar sem efeito; backup, comentários e confirm true; G-COMP/G-E2E/G-PY |
| F8-018 | §3.11: revision inteiro seguro não negativo; revision atual/próxima e envelopes coerentes | 2, 6, 9 | DTOs e máquina de estados | Limites MAX_SAFE_INTEGER, booleanos/frações, snapshots incompatíveis, nenhuma coerção; G-TYPE/G-UNIT |
| F8-019 | §3.11: uma escrita por vez, expected_revision do snapshot confirmado, sem rebase por polling | 6–9 | Transporte e coordenador de sessão | Cliques concorrentes, duas abas, polling atrasado e resposta de geração anterior; G-COMP/G-E2E |
| F8-020 | §3.12: todos os 409, reload busy e recusas têm ações explícitas e não apagam rascunho silenciosamente | 6–9 | Estados e mensagens privadas | Matriz de erros completa, refresh consciente, retry só por decisão humana após reconciliação; G-UNIT/G-E2E |
| F8-021 | §3.12: pós-commit aplicado, durabilidade incerta, erro interno e resultado desconhecido distintos; sem retry/rollback automático | 6–9 | Reconciliação de escrita | Falhas antes/depois de replace, resposta perdida e verificação disco/digest/runtime/IDs/auditoria; G-PY/G-E2E/G-SEC |
| F8-022 | §3.13: Admin API/PG indisponíveis, loading/erro/retorno, teclado, foco, responsividade e acessibilidade | 5–9 | Telas, transporte e controles | Startup PG ausente, PG cai após start, API encerra, viewport 320 px e zoom 200%, foco/labels/teclado/leitor; G-COMP/G-E2E |
| F8-023 | §3.14: vocabulário público permitido fechado; modelos, campos/chamadas/mensagens de negócio privados | 2, 4–9 | Autor privado e bootstrap público | Inspeção literal e decodificada dos bytes finais contra schemas/rotas/registry/enums; contraprovas de concatenação/encoding; G-UNIT/G-SEC |
| F8-024 | §3.14: exceções lexicais e exposição residual apenas as expressamente aprovadas | 2, 9 | Validador de artefatos públicos | Allowlist exata e fixtures proibidas, sem ampliar para passar gate; revisão D-062; G-UNIT/G-PKG |
| F8-025 | §3.15: raiz format/models/calls/views/editors/bindings/messages; 8 leituras, validate e 10 escritas autorizadas | 2, 6–9 | Catálogo privado e seus tipos | Igualdade integral, contratos de corpo/resposta, sem PUT /config ou chamadas adicionais; G-TYPE/G-UNIT/G-SEC |
| F8-026 | §§3.15–3.16: interpretador fechado sem código/HTML/URLs livres, projeções limitadas e sem token no corpo | 2, 5–9 | Interpretador declarativo | Propriedades desconhecidas, tipos errados, prototype pollution, ciclos, URLs e projeções hostis; G-TYPE/G-UNIT/G-SEC |
| F8-027 | §3.16: 6 vistas, 8 editores, 19 calls, 128 models, profundidade 16, 512 controles e limites estruturais completos | 2, 5, 9 | Validadores servidor/cliente e renderer | Limite e limite+1, chaves perigosas, validação pré-bind, hash privado e nenhuma operação antes de validar; G-UNIT/G-SEC |
| F8-028 | §4.1: token/rascunhos só memória; novo login após reload, logout/pagehide/pageshow/BFCache invalidam sessão e DOM | 5–9 | Sessão e lifecycle do documento | G-COMP/G-E2E/G-SEC; token sentinela, storage vazio, navegação/histórico/BFCache, respostas tardias sem ressuscitar estado |
| F8-029 | §4.2: esquema http, Host loopback e porta do bind; parsing estrito, sem equivalência por DNS/alias | 3–4, 9 | Parser de Host e origem | Casos válidos exatos e inválidos por esquema/host/porta, IPv4/IPv6, porta implícita só 80 real, duplicados/malformados; G-HTTP/G-SEC |
| F8-030 | §4.2: Origin e Referer concordam exatamente; ausentes não concedem autenticação; Sec-Fetch-Site não é credencial | 4, 9 | Política de navegador | Externo/null/múltiplo/ambíguo, same-site/cross-site e headers ausentes/forjados; 403 antes de auth; G-HTTP/G-E2E |
| F8-031 | §§4.2–4.3: fetch normativo, URL validada antes de Authorization; sem CORS/preflight/proxy/redirect credenciado | 4, 6, 9 | Transporte público e servidor | mode cors, credentials omit, redirect error, no-store/no-referrer; interceptar pedidos reais e redirects sem vazamento; G-E2E/G-SEC |
| F8-032 | §4.4: todo conteúdo administrativo como texto; sem innerHTML, HTML dinâmico, scripts/fontes/assets externos | 2, 5–9 | Renderer e recursos locais | XSS em match, parâmetros e mensagens, handlers/URLs perigosas e nenhum request externo; G-COMP/G-E2E/G-SEC |
| F8-033 | §4.5: threat model completo, riscos residuais e fronteiras de confiança | 2–9 | Revisão de segurança transversal | Todos os ataques e limites da tabela §4.5 rastreados nas contraprovas; não alegar proteção contra navegador/processo comprometido |
| F8-034 | §§4.1, 6.7: token nunca em URL/cookie/HTML/bundle/log/erro/storage/artefato de teste | 2, 4–9 | Bootstrap, transporte e harness | Sentinelas nos bytes, DOM fora do input/sessão permitidos, logs, headers indevidos e storages; sem HAR/traces/vídeos/screenshots administrativos; G-SEC |
| F8-035 | §§3.1, 3.4, 4: secrets só configured/missing, nunca valor ou máscara parcial | 2, 5–9 | Modelos/vistas privadas | Contraprovas DSN/HMAC/token; sem campos de credencial de banco ou valores em mensagens; G-TYPE/G-E2E/G-SEC |
| F8-036 | §§3.1, 3.8, 3.11: sem edição de IDs, revision ou allowed_pg_functions | 2, 5–9 | Controles e projeções | Campos readonly, ausência de controle editável e payload mutável, requests hostis recusados pela API; G-TYPE/G-E2E/G-PY |
| F8-037 | §§3.1, 5.6: sem frontend MCP, SQL, resultado, auditoria consultável ou mudança de domínio | 2–9 | Catálogo, dependências e separação de planos | AST/imports existentes, rotas/ações fechadas, nenhum endpoint/store/SQL editor, stdout MCP limpo; G-PY/G-SEC |
| F8-038 | §5.1: inventários exatos 20/28 com UI off e 24/36 com UI on | 4, 9 | Registro fechado de rotas | Igualdade por rota e método; não testar apenas inclusão, atualizar matriz adversarial da Etapa 11; G-HTTP/G-SEC |
| F8-039 | §§5.1–5.3: 3 recursos públicos GET/HEAD canônicos, presentation autenticada e nenhuma docs/rota adicional | 4, 9 | Dispatcher de recursos e auth | Produto cartesiano rota/método/token válido/ausente/inválido; schema/estado privado jamais no 401; G-HTTP/G-E2E |
| F8-040 | §5.2: Host, origem, tamanho declarado, auth/exceção pública, media type, corpo e routing na ordem aprovada | 4, 9 | Middlewares condicionais | Múltiplas violações simultâneas, 400/403/413/401/415 e limite streaming autoritativo quando consumido; G-HTTP/G-PY |
| F8-041 | §5.3: query pública não vazia 404; privada sem auth 401 e com auth 404; query vazia ASGI admitida | 4, 9 | Dispatcher raw_path/query_string | Queries, delimitador vazio e tokens em query nunca aceitos; G-HTTP/G-SEC |
| F8-042 | §5.3: raw_path exato, sem decodificar/normalizar/redirecionar para conceder exceção pública | 4, 9 | Fronteira de recursos | Trailing slash, percent encoding, traversal, barras invertidas, lookalikes; ASGI bruto e normalização do browser separadamente; G-HTTP/G-E2E |
| F8-043 | §5.3: métodos inválidos/OPTIONS seguem autenticação e recusas anteriores, sem CORS | 4, 9 | Fronteira e serializador de erros | 401/403/405 e 415 quando aplicável, nenhuma rota OPTIONS ou header CORS; G-HTTP/G-SEC |
| F8-044 | §§5.3–5.4: recursos UI sem AdminAudit, contador, validação ou acesso PostgreSQL | 4, 9 | Handlers de bytes imutáveis | Instrumentação de todos os sucessos/erros/recusas; zero efeito e zero auditoria de UI; G-PY/G-HTTP |
| F8-045 | §5.4: bytes de sucesso exatos, sem interpolação; erro canônico com detail fixo e sem fields/revision/applied | 4, 9 | Respostas e serializador | Comparação literal completa para cada status, segredo sentinela, erro interno sanitizado; G-HTTP/G-SEC |
| F8-046 | §5.4: HEAD igual a GET em status/auth/headers/Content-Length, sem corpo inclusive no erro | 4, 9 | Servidor/HEAD | Servidor real e ASGI para sucessos e recusas; G-HTTP/G-E2E |
| F8-047 | §5.4: headers e MIME exatos, no-store/nosniff/no-referrer/DENY/CORP/COOP/Permissions-Policy | 4, 9 | Política de resposta | Tabela completa por sucesso/erro/admin/UI e flag on/off; G-HTTP/G-SEC |
| F8-048 | §5.4: CSP HTTP exata, sem unsafe-inline/eval, data/blob ou reporting; JSON/erros restritos | 4–5, 9 | Headers e DOM | Comparação literal e violações reais com inline/style/event handler/recurso externo/frame bloqueados; G-E2E/G-SEC |
| F8-049 | §5.4: sem Set-Cookie/Server/ETag/Last-Modified/Allow novo/CORS, 304/206/compressão | 4, 9 | Respostas HTTP | Headers proibidos ausentes, condicionais/Range retornam representação completa autorizada; G-HTTP/G-SEC |
| F8-050 | §5.5: limites UTF-8 inclusivos, manifesto 4 entradas fechado, hashes e leitura máximo+1; pacote imutável verificado | 2–3, 9 | Build, manifesto e carregador | Todos os máximos e excesso, duplicados/campos extras/path/hash/UTF-8, recurso ausente; stdout/exit/stderr exatos e bytes em memória estáveis; G-UNIT/G-PKG |
| F8-051 | §5.6: mudanças só na fronteira condicional aprovada, sem schemas/runtime/persistência/auditoria/MCP | 3–4, 9 | Fronteira e bootstrap | Revisão de diff, regressões da Fase 7 e matriz Etapa 11 nos dois modos; G-PY/G-SEC |
| F8-052 | §6.1: Node 24.20.0, npm 11.19.0, Playwright 1.63.0 e TypeScript 5.9.3 fixados | 2, 9 | Toolchain de desenvolvimento | Versões/lock conferidos; nenhuma dependência runtime JS ou instalação em execução; G-TYPE/G-PKG |
| F8-053 | §6.1: JSDoc/checkJs strict/noEmit e opções exatas, contratos privados completos, unknown validado, sem escapes | 2, 5–9 | Tipos de DTOs, estados e interpretador | G-TYPE; contraprovas de uso inválido e conformidade de todas as operações, sem any/ts-ignore/casts burlando validação |
| F8-054 | §6.2: build determinístico local, lock v3, recursos Python embarcados e nenhuma CDN/runtime Node | 2, 9 | Build e distribuição | Builds repetidos iguais, inventário exato, wheel/sdist instalados fora do checkout, execução sem toolchain; G-PKG |
| F8-055 | §6.3: unidades/contratos e limites com contraprovas, não só caminho feliz | 2–9 | Harness Node/Python | Gramática, catálogo, projeções, tipos, estados, fronteira e falhas; G-UNIT/G-TYPE/G-PY |
| F8-056 | §6.3: inventários privados e públicos gerados/verificados contra fontes de negócio, sem duplicação permissiva | 2, 4, 9 | Verificadores de contrato | Divergir fonte deliberadamente faz gate falhar; não aceitar contém-pelo-menos; G-UNIT/G-SEC |
| F8-057 | §6.4: bytes públicos finais examinados também após decodificação; segredo/schema não escondido por encoding | 2, 9 | Verificador de artefatos | Contraprovas literais, concatenação, escapes e arquivos finais empacotados; G-UNIT/G-PKG/G-SEC |
| F8-058 | §6.5: testes de componentes com runner Playwright padrão, fixtures locais e acessibilidade | 5–9 | Harness de componentes | Estados/controles/foco/teclado/conteúdo hostil; sem pacote experimental ou recurso externo; G-COMP |
| F8-059 | §6.6: Chromium 153.0.8010.12, Firefox 155.0 e WebKit 26.6 reais; PostgreSQL real | 4–9 | Harness de browser e servidor real | Matriz completa e versões distribuídas pelo pin aprovado; sem dispensar browser ausente; G-E2E |
| F8-060 | §6.7: CSRF, DNS rebinding/origem/headers, token inválido, caminhos hostis, XSS e leakage | 4–9 | Suíte adversarial de navegador | Todas as classes adversariais da subseção, fontes externas e sentinelas, sem gravar segredos; G-HTTP/G-E2E/G-SEC |
| F8-061 | §6.7: concorrência, fault injection e efeitos em arquivo/digest/runtime/IDs/auditoria | 6–9 | Harness de integração existente ampliado | Mesma revision em concorrência, busy, falhas pre/post replace, resposta perdida; nenhum endpoint de fault injection no produto; G-PY/G-E2E |
| F8-062 | §6.8: gates acumulados verdes, DSN/browser real, nenhum finding convertido em skip/xfail | 2–9 | Processo de validação | Registrar comandos, versões, contagens medidas e skips condicionais; bloquear avanço em falha; todos os gates devidos |
| F8-063 | §7.1: ordem incremental 2 tipos/build; 3 startup; 4 fronteira; 5 leitura; 6 estados; 7 CRUD; 8 reorder/db/sql; 9 fechamento | 2–9 | Plano de implementação | Nenhuma funcionalidade antes da fronteira aprovada; revisão de escopo por etapa e suíte acumulada verde |
| F8-064 | §7.2: todos os critérios de aceite, sem finding novo pendente de tratamento/aprovação | 9 | Revisão final | Evidências completas de todos os IDs, pacote instalado e execução de todos os gates; nenhuma conclusão só documental |
| F8-065 | §7.3: rollback pela flag/restart ou pacote anterior compatível; sem desfazer config/adoção/IDs/revision | 3–4, 9 | Lifecycle e procedimento operacional | Confirmar ausência de 4 rotas, rejeição Origin/Referer por presença, headers/erros antigos e clientes nativos; G-HTTP/G-PKG/G-E2E |

## Conferência de cobertura e encerramento de etapa

A matriz cobre todas as subseções normativas: §§1.1–1.5, 2, 3.1–3.16,
4.1–4.5, 5.1–5.6, 6.1–6.8 e 7.1–7.3. A aprovação de §8 está registrada
em D-061–D-064. A referência a uma subseção abrange seus requisitos subordinados;
nenhuma tabela de headers, limites, erros ou ataques é opcional.

Na implementação, registrar por ID o teste concreto e a execução que prova o
requisito, reutilizando cobertura existente quando suficiente. Enquanto o teste
não existir ou o gate não passar, a linha permanece pendente. Não preencher
resultado de UI com a baseline Python da Etapa 1. Ao fechar cada etapa, revisar
os IDs que ela entrega e executar todos os gates acumulados aplicáveis.


## Entrega da Etapa 2 e pendências preservadas

**Etapa 2 concluída; gates aplicáveis aprovados.** Os resultados medidos
estão na evidência da etapa. O status abaixo descreve implementação de fundação,
não conclusão integral dos IDs que também exigem Etapas 3–9.

| IDs | Componente entregue | Teste/gate concreto | O que continua pendente |
|---|---|---|---|
| F8-001, 006, 054 | package-data/MANIFEST.in, recursos em `maskgw.admin.ui`, LF fixo por `.gitattributes` | G-PKG: inventário de wheel/sdist e instalação isolada fora do checkout | Processo/origem/lifecycle e entrega HTTP |
| F8-007–018, 025, 035–037, 053 | `frontend/private/contracts.d.ts`, tipos derivados dos onze contratos, união UiWriteContract de dez, defaults, seis vistas/oito editores estáticos | G-TYPE; `contracts.js`, oito contraprovas de compilação e paridade de catálogo em Node/Python | Renderização, DTOs recebidos em sessão, formulários, transporte e efeitos |
| F8-023–024, 032, 034, 056–057 | `generate.py` deriva 193 entradas; `inspect.js` examina bytes/literais/identificadores/concatenações | G-UNIT/G-SEC: contraprovas em cada recurso e encodings; inspeção no build e npm run inspect | Respostas HTTP reais, DOM/XSS e lifecycle de token |
| F8-025–027, 033, 055 | `protocol.py` e `protocol.js`; 110 modelos, 19 chamadas, 35 controles, validação independente de grafo/catálogo | `test_admin_ui_resources.py`, `protocol.test.js`: chaves/refs/ciclos/defaults/uniões/projeções/templates/protótipos e limites 128/16/512 | Interpretador de rendering/projeções e conferência Web Crypto antes de sessão |
| F8-038–039, 051, 056 | Catálogo privado `_catalog.py` comparado por igualdade; fontes HTTP atuais preservadas | `test_package_catalog_is_exact_and_independent`, `test_catalog_refuses_valid_but_unauthorized_call`, `test_ui_loader_has_no_runtime_or_http_dependency` | Inventário HTTP condicional 24/36 e autenticação das novas rotas |
| F8-050 | `resources.py`, quatro recursos, manifesto interno, SHA-256 privado/manifesto/modelos; carga limitada e imutável | Corrupção/ausência/UTF-8/JSON/duplicatas/tamanhos máximos+1, manifesto reancorado hostil e erro sem cadeia | Chamar o validador na ordem de startup da Etapa 3 |
| F8-052–054, 062–063 | Node/npm/TypeScript/Playwright fixados, lock v3, npm ci; sem bibliotecas de runtime | Versões medidas; G-TYPE; dois builds idênticos em 14 arquivos; G-PKG; G-PY completo | Executar gates acumulados novamente em cada etapa futura |

`presentation.json` é metadado estático, não snapshot do Gateway. O HTML é
somente shell e o JS só verifica o protocolo: não há DOM dinâmico, fetch,
Storage, polling, formulários funcionais, CRUD ou execução das projeções.
Não marcar F8-028–031, 040–049, 058–061 ou 064–065 como concluídos por esta
entrega: seus comportamentos de servidor/navegador/operação ainda não existem.
O gate PostgreSQL da etapa reproduz e protege o produto Python existente.

## Entrega da Etapa 3

**Concluída; gates acumulados aprovados.** O quadro da Etapa 2 preserva
sua entrega histórica. Os requisitos normativos e as pendências das Etapas 4–9
não mudam. Resultados medidos: `PHASE-8-STAGE-3-VALIDATION.md`.

| IDs | Entrega nesta etapa | Prova concreta | Limite restante |
|---|---|---|---|
| F8-002 | RawSettings, EnvRawSettings e MappingRawSettings; flag exata e dependência | `test_exact_raw_flag`, `test_process_uses_raw_flag_without_querying_secret_provider`, `test_secrets_still_normalize_and_raw_source_does_not`, `test_ui_requires_admin_before_settings_or_resources` | Nenhuma entrega HTTP ou sessão |
| F8-003, 027, 050 | settings e load_resources antes do filesystem; bytes conservados | `test_invalid_admin_settings_precede_assets`, `test_direct_composition_cannot_bypass_preconditions`, todas as ausências/corrupções e incompatibilidades em `test_admin_ui_startup.py` | Uso dos bytes pelo HTTP na Etapa 4 |
| F8-004 | ownership e lifecycle existente preservados | `test_positive_startup_order_and_shutdown`, `test_owned_bytes_survive_disk_changes_and_repr_is_boolean_only`, `test_partial_failure_releases_thread_socket_runtime_and_lock` | Regressões acumuladas nas etapas seguintes |
| F8-005, 029, 051, 065 | UI off com os mesmos bytes; UI on ainda sem rotas ou políticas novas | `test_http_surface_remains_phase_seven_and_disabled_repr_exact`: 40 respostas reais por modo contra d080886; `test_stage_three_does_not_change_http_policy_or_secret_normalization` e separação de planos | Origem/CSP/headers/rotas condicionais somente na Etapa 4; rollback final na Etapa 9 |
| F8-054, 062–063 | gates acumulados, recursos inalterados da Etapa 2 | npm ci/typecheck/Node/build/inspect; 14 hashes contra o commit aprovado; Python completo/PostgreSQL real/Ruff/format/mypy/diff | Browsers reais somente no marco devido da Etapa 4 |


## Entrega da Etapa 4

Concluída; gates acumulados aprovados em `PHASE-8-STAGE-4-VALIDATION.md`.
Python: 3.804 coletados, 3.796 aprovados e oito skips POSIX; 75 Node e 21
browsers aprovados. Ruff/format/mypy strict verdes em 135 arquivos.
Os quadros anteriores são históricos. Este quadro não encerra requisitos de
sessão, rendering, CRUD, concorrência ou pacote instalado da Etapa 9.

| IDs | Entrega desta etapa | Prova concreta | Limite restante |
|---|---|---|---|
| F8-001, 004, 006, 037, 051 | Composition root passa bytes pré-validados; HTTP adota cópia imutável; nenhum loader no handler | `test_handlers_keep_immutable_snapshot_of_mapping`, startup/falha parcial/shutdown acumulados e `test_plan_separation.py` | Lifecycle de documento/sessão na Etapa 5 |
| F8-005, 065 | Ramo UI off original; rollback pela flag e restart | 40 respostas literais contra `phase7-ui-off.json` e repr exato; dez fontes compartilhadas com hash protegido | Rollback operacional final de pacote na Etapa 9 |
| F8-029–030, 033, 060 | Parser literal de Host, origem e Referer exatos, Fetch Metadata e forwarding ignorado | `test_host_parser_*`, `test_origin_refusals`, `test_both_origins_must_agree_and_duplicates_refused`, `test_fetch_metadata`, duplicatas e `test_server_parser_vs_asgi_and_loopback_aliases` | Regressão acumulada; não alegar defesa contra processo/navegador privilegiado comprometido |
| F8-038–043 | Quatro rotas condicionais; exceção raw canônica; query, variantes, métodos e precedência | `test_inventory_exact_twenty_or_twenty_four`: 20/28 e 24/36; `test_http_product`: 1.224 combinações; `test_precedence`, `test_media_type_before_routing` | Manter inventário fechado nas próximas etapas |
| F8-044–049 | Bytes, MIME, HEAD, erros fixos, duas CSPs, headers exatos e nenhuma auditoria/estado/PG de UI | `Untouchable` verifica zero acesso em toda a matriz; falha interna pública/privada; `test_head_early_refusals_equal_get`, servidor real com Range/condicionais, API JSON, headers proibidos e controle CSP real | DOM/XSS armazenado e controles de rendering só nas Etapas 5–9 |
| F8-023–024, 027, 031, 034, 056–057 | Transporte explícito mínimo, origem antes de Authorization, hash Web Crypto e gramática antes do negócio | `transport.test.js`; `transport.spec.js`: fetch GET/POST real, redirects reais sem encaminhamento, hash/metadata inválidos, CSRF, token/log/storage; 193 termos privados e reconstrução continuam recusados | Sem sessão, DTO de tela, transporte granular, máquina de estados ou escrita UI |
| F8-052–055, 059, 062–063 | Pins/lock preservados; builds repetidos; browsers reais; gates acumulados | npm ci, typecheck strict/checkJs/noEmit, Node, build/inspect, Playwright três engines, Python inteiro com PostgreSQL 16 real, Ruff/format/mypy/diff | Etapas 5–9 e publicação dependem de autorização |

A autorização da Etapa 4 substitui somente a asserção histórica de que UI on
não muda HTTP. A fixture congelada não foi editada: sua comparação literal
continua obrigatória em UI off. Os hashes de `app.py` e `server.py` deixam de
ser exigidos por identidade porque suas mudanças condicionais foram aprovadas;
os demais dez hashes permanecem protegidos. Não houve skip/xfail para essa
transição. A matriz nova comprova o contrato on por igualdade e bytes completos.
