# Fase 8 — matriz de rastreabilidade normativa

**Estado:** concluída; Etapas 1–9 revisadas, aprovadas e publicadas em `42cd2df`. **Atualização:** 2026-09-22.
A autorização documental da Fase 9 não altera requisitos ou evidências desta
matriz.
**Fonte normativa integral:** [PHASE-8-SPEC.md](PHASE-8-SPEC.md), aprovada
integralmente, com decisões [D-061 a D-064](DECISIONS.md#d-061--ui-administrativa-embarcada-opt-in-e-na-mesma-origem).

Esta matriz é um índice verificável, não uma versão reduzida da especificação.
Cada linha cobre **todos** os requisitos, listas, limites e contraprovas das
subseções indicadas, inclusive quando a descrição abaixo não os repete.
O texto integral prevalece. O mapeamento é muitos-para-muitos: um gate comum
não dispensa os testes específicos. Os quadros das Etapas 1–8 são históricos e
conservam as pendências existentes em cada entrega. O quadro de encerramento
da Etapa 9 registra a comprovação final de todos os 65 requisitos, com os
limites explícitos de plataforma, BFCache e acessibilidade da evidência.

A Etapa 9 foi autorizada após revisão e publicação da Etapa 8. A tabela
normativa mantém os componentes previstos;
o quadro de entrega identifica quais já existem, sem antecipar APIs.
As seções 1–2 e 8 também fundamentam D-061–D-064; a seção 7 fixa ordem, aceite
e rollback. Evidências: [Etapa 1, histórica](PHASE-8-STAGE-1-VALIDATION.md) e
[Etapa 2, histórica](PHASE-8-STAGE-2-VALIDATION.md) e
[Etapa 3, histórica](PHASE-8-STAGE-3-VALIDATION.md) e
[Etapa 4, histórica](PHASE-8-STAGE-4-VALIDATION.md). [Etapa 5, histórica](PHASE-8-STAGE-5-VALIDATION.md). [Etapa 6, histórica](PHASE-8-STAGE-6-VALIDATION.md). [Etapa 7, histórica](PHASE-8-STAGE-7-VALIDATION.md).
[Etapa 8, histórica](PHASE-8-STAGE-8-VALIDATION.md). Rodada atual:
[Etapa 9](PHASE-8-STAGE-9-VALIDATION.md).

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
| F8-016 | §3.9: config:validate sem expected_revision, raiz candidata e projeção de novos itens sem IDs/revision | 2, 6–9 | Projeção privada e validação | G-TYPE/G-UNIT/G-E2E/G-PY; contrato raiz, proteção preservada e nenhum efeito em disco/runtime/revision |
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


## Entrega da Etapa 4 (registro histórico, publicada)

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

## Entrega da Etapa 5

A Etapa 4 foi publicada sem emenda em
`7e8e39988b38438128a51fc414ecae68cdde01c1`. Esta tabela identifica a entrega
exclusiva de leitura; não encerra requisitos de escrita das Etapas 6–9.
Evidência medida: [Etapa 5](PHASE-8-STAGE-5-VALIDATION.md).

| IDs | Entrega concreta | Prova/gate | Pendência preservada |
|---|---|---|---|
| F8-007–010, 022, 058 | `screen.js`, seis vistas autenticadas e seleção em memória; leitura declarada distinta de proteção efetiva | `reading.spec.js`: login explícito, seis vistas/teclado/URL, vazio/loading/erro/retry, polling visível serial, PG/API indisponíveis, zoom/320 px/reduced motion | Ações de escrita/validação/adoção/CRUD ausentes; Etapas 6–9 |
| F8-018, 026–027, 053, 055 | `reader.js` interpreta somente modelos/bindings privados; unknown validado antes do estado, revisions seguras, envelopes e listas coerentes | `reader.test.js`, `transport.test.js`, DTOs unsafe/shape/incoherent e snapshots diferentes em browser; G-TYPE | Revision de escritas, expected_revision e reconciliação: Etapa 6 |
| F8-028, 034, 058, 060 | Token na closure, geração/cancelamento e erase de DOM; nenhum store/URL/global | `reading.spec.js` e `lifecycle.spec.js`: logout/401/pagehide/pageshow/reload, metadata/leitura tardia, sessão nova, storage/atributos/logs; Node ignora abort propositalmente e não ressuscita | Rascunhos não implementados. BFCache nativo adicional Chromium; eventos persisted nos três; limite de automação Firefox/WebKit documentado |
| F8-023–027, 032–036, 048, 057 | DOM somente texto, vocabulário fechado, secrets só enum de estado, todos os controles readonly | XSS persistido em outra sessão, reflexão em cada string dos DTOs, campos inválidos recusados; controles positivos de execução/rede acumulados; 193 termos/contraprovas | Editores, projeções e mensagens de escrita não executados |
| F8-004–005, 029–031, 037–051, 065 | Fronteira/startup da Etapa 4 inalterados; telas usam somente GETs já existentes | G-PY/G-HTTP; fixture off literal, matriz 20/28 e 24/36, testes de planos; harness readonly reprova escrita/audit/efeitos | Fechamento/rollback final da Etapa 9 |
| F8-052–055, 059, 062–063 | Pins/lock preservados, build duplo e pacote isolado, gates acumulados | G-TYPE/G-UNIT/G-COMP/G-E2E/G-PKG/G-PY; resultados medidos na evidência | Etapas 6–9 e publicação desta etapa aguardam autorização |

Medição final da Etapa 5: 99 testes Node e 78 testes de navegador aprovados;
3.804 Python coletados, 3.796 aprovados e oito skips POSIX, sem DSN ausente
ou deselects. PostgreSQL 16.15 real; typecheck, Ruff/format/mypy strict, build
duplo/193 termos e wheel/sdist isolados aprovados. Tempos e hashes na evidência.

## Entrega da Etapa 6

Concluída; gates acumulados aprovados em `PHASE-8-STAGE-6-VALIDATION.md`. A Etapa 5
foi publicada sem emenda em `0d42f5d0d9a835177dd1c5e4a6c608161f585896`.
Os quadros anteriores são evidências históricas. As seis telas e a fronteira
HTTP continuam intactas. Não há controles de escrita, adoção, validação pela
tela, formulários, CRUD, reorder ou edição de database/SQL nesta entrega.

| IDs | Componente/contrato concreto | Prova nesta etapa | Limite preservado |
|---|---|---|---|
| F8-018, 026, 053, 055 | `commands.js`, `reader.js`: inteiros seguros, próxima versão, versões coerentes e binding privado de current_revision | `commands.test.js`: matriz de tipos/limites, overflow e envelopes contraditórios; contraprovas de `Flow`, `Command` e `Outcome` em `protocol.test.js` | Schemas Python e runtime inalterados |
| F8-019–021, 061 | `coordinator.js`: base/rascunho/comando congelados, uma pendência, observação separada, revisão humana e releitura | `coordinator.test.js`: duplo clique, concorrência, polling, busy, conflito, durabilidade, resposta perdida, sucesso com releitura falha, invalidação de base após segunda releitura falha, duas sessões e respostas fora de ordem | Integração dos controles e efeitos reais das escritas nas Etapas 7–9 |
| F8-020–021, 023, 025, 031 | `transport.js` e `commands.js`: catálogo privado, projeção fechada, envelopes antes de mapear por mensagens privadas | Dez operações em `commands.test.js`, DELETE JSON, opções Fetch, zero requests antes de verificar corpo/destino/identidade, erro/timeout/JSON/media type em `coordinator.test.js` | Sem PUT /config, sem interpolação livre, sem retry/rollback automático |
| F8-026–028, 034, 036 | Cópia profunda congelada; protótipos/accessors/chaves desconhecidas recusados; identidade canônica derivada de modelo privado | Projeções protegidas, token no corpo, getters/ciclos/símbolos, identidade hostil, DTOs imutáveis; expiração do transporte limpa o coordenador | Token somente na closure, nenhuma edição de IDs/revision/proteções |
| F8-019–022, 028, 058–061 | `browser/coordinator.spec.js`: componentes reais do ESM com transporte controlado | Oito cenários de desfecho e quatro casos de cleanup nos três engines; servidor/harness real permanece readonly e exige zero efeito/auditoria | Nenhuma mutação chega ao backend nesses casos; regressões reais de leitura/HTTP permanecem acumuladas |
| F8-004–005, 029–030, 037–051, 065 | Python de produto, startup, HTTP, renderer e pins preservados | Suíte Python/PostgreSQL integral, matriz HTTP, fixture off e regressões de leitura/lifecycle; diff de escopo | BFCache Firefox/WebKit com a limitação já aceita; fechamento final na Etapa 9 |
| F8-023–027, 050, 052–057, 062–063 | Build duplo, manifesto/modelos reancorados e inspeção pública sem exceções | npm ci, checkJs strict/noEmit, Node, `node --check` no ESM final, 193 termos, wheel/sdist fora do checkout e sem Node/npm | Não publicar Etapa 6 nem iniciar Etapa 7 nesta rodada |

Medição final da Etapa 6: 176 testes Node e 114 testes de navegador aprovados; 3804 Python coletados, 3796 aprovados e oito skips POSIX. PostgreSQL 16.15 real, sem deselect/skip por DSN. Typecheck, build duplo/193 termos, pacote isolado e Ruff/format/mypy strict aprovados. Evidência detalhada em `PHASE-8-STAGE-6-VALIDATION.md`.

## Entrega da Etapa 7

A Etapa 6 foi publicada sem emenda em
`db33fa770e1b675ee23ad554a84c93a7e9e2f358`. Esta entrega conecta somente adoção
legada, validação explícita e CRUD granular; os quadros anteriores preservam
seus limites históricos. Etapas 8–9 e publicação desta etapa não autorizadas.
Evidência: [Etapa 7](PHASE-8-STAGE-7-VALIDATION.md).

| IDs | Componente/contrato concreto | Prova/gate nesta entrega | Limite preservado |
|---|---|---|---|
| F8-007, 011–013, 025–027, 035–036 | `author.js`, controles privados e `workbench.js`: dois perfis CRUD, defaults distintos, oito editores/registry, parâmetros fechados e match literal | `author.test.js`, `editing.spec.js`: corpos completos, limites/dependências, unknown bloqueado, proteção de IDs/revision, posição preservada e cancelamentos | Reorder de regras e database/SQL: Etapa 8; nenhum reorder de exceptions |
| F8-016, 018, 026, 055 | Candidato raiz transitório, sem IDs/revision/expected_revision, conservando valores protegidos; quatro booleanos exatos | Node: base imutável, múltiplos itens sem IDs, alteração/exclusão, getters/protótipos; browser: validação explícita, nenhuma escrita/efeito em arquivo/runtime/digest/contador, reasons conhecidos, invalidação e resposta tardia | Validação não salva, não reserva revision, não testa conexão nem prova proteção integral |
| F8-017, 028, 058 | Adoção com aviso privado completo, checkbox falso e gesto final único | Browser: cancelamento, falso, sucesso, duas abas/já adotado, backup original sem exposição e releitura; regressões Python de conflito/adoption | Nenhuma adoção implícita; legado só leitura/validação |
| F8-019–021, 061 | Coordenador por edição; release sem fechar sessão; base/rascunho preservados; bloqueio durável na sessão após unknown/uncertain | Browser real: duplo clique, duas abas, conflito/review, busy com lease real, falha antes de persistir, reload inválido, pós-commit incerto, resposta perdida e readback falho; Node/componentes acumulados | Sem fila/retry/rebase/rollback automático; revision maior não prova autoria |
| F8-022, 028, 032–034, 058–060 | Formulários/diálogos semânticos, foco preso/restaurado, descarte explícito e DOM somente texto | Três engines: teclado, 320 px, escala 200%, reduced motion, XSS persistido, reasons hostis, 401/pagehide/pageshow limpam formulário e diálogo aninhado; controles positivos acumulados | BFCache nativo adicional Chromium; limite Firefox/WebKit já documentado |
| F8-004–005, 029–031, 037–051, 062, 065 | Fronteira/backend intactos; harness privado de edição usa composition root e PG reais | G-PY/G-HTTP, fixture UI off literal, planos, audit por operação/alvo/outcome/revisions, HTTP → runtime → MCP e restart | Nenhuma rota, SQL UI, auditoria consultável, schema ou domínio alterado; fechamento da Etapa 9 futuro |
| F8-023–027, 050, 052–057, 059, 063 | Novos controles/modelos privados e JS/CSS reancorados; gramática, catálogo de chamadas, pins e vocabulário preservados | Instalação congelada; checkJs strict/noEmit; Node; 14 saídas iguais; 193 termos; wheel/sdist isolados; três engines/PG16 e Python inteiro | Não publicar Etapa 7 nem iniciar Etapa 8 nesta rodada |


Medição final da Etapa 7: 195 testes Node e 156 de navegador aprovados (52 por
engine), sem skips/retries; 3808 Python coletados, 3800 aprovados e oito skips
POSIX. PostgreSQL 16.15 real, sem deselect/skip por DSN; Ruff/format/mypy strict
em 137 arquivos, tipagem, build duplo/193 termos e wheel/sdist isolados verdes.
A falha inicial de startup MCP e o diagnóstico/repetição integral posteriores
estão discriminados em `PHASE-8-STAGE-7-VALIDATION.md`. Não publicar esta etapa
nem iniciar a Etapa 8 sem revisão e autorização.

## Entrega da Etapa 8

Etapa 7 publicada exatamente em `57cc7522642d3fe3dddd10187b996ba71fc38e3f`.
Esta entrega é exclusivamente reorder de regras, database e SQL aditivo.
Evidência: [Etapa 8](PHASE-8-STAGE-8-VALIDATION.md). Nenhum item da Etapa 9.

| Requisitos | Componentes entregues | Provas/gates | Limite preservado |
|---|---|---|---|
| F8-011–012, 018–020, 022, 036 | Perfis declarativos de permutação; ordem global independente do filtro; teclado, posições 1-based, revisão e confirmação | `batches.test.js` / `batches.spec.js`: malformadas, duplicadas, incompletas, estrangeiras e obsoletas; cancelamento, abas, conteúdo e IDs | Somente rules:reorder; nenhuma reordenação de exceptions ou PUT /config |
| F8-014, 025–027, 035–036 | Dois controles inteiros; modelo fechado e corpo raiz completo | Limites extremos, tipos/extras sem request; preservação dos demais campos e efeito MCP | Sem DSN, coerção ou edição parcial |
| F8-015–016, 036 | Inclusões literais e candidato base+rascunho; lista declarada e proteção efetiva readonly | Duplicatas, caixa, Unicode e releitura Python; nenhum allowed_pg_functions nas mutações | Sem remoção, renomeação ou casefold autoritativo no JS |
| F8-016, 019–021, 028, 034 | Coordenador existente, snapshot/revision/draft, validação explícita e bloqueio da sessão | Node acumulado e browsers: conflito/busy, respostas perdidas/readback falho/durabilidade, 401 e lifecycle | Sem escrita implícita, fila, retry/rebase/rollback automático |
| F8-022–024, 032–038, 050, 052–057, 059, 063 | Projeções e renderer de texto; mesmos catálogos/gramática/pins/HTTP | XSS filtrado, teclado/320 px, 193 termos, dois builds, pacotes isolados, engines fixados, PG16 e Python completo | Nenhuma expansão de planos, rotas, transporte, auditoria, MCP ou Etapa 9 |

Medição final da Etapa 8: 241 testes Node e 189 de navegador aprovados (63 por
engine), sem skips/retries; 3808 Python coletados, 3800 aprovados e oito skips
POSIX, PostgreSQL 16.15 real, sem deselect/skip por DSN. Tipagem estrita, npm ci,
build duplo/193 termos, wheel/sdist isolados sem Node/npm, Ruff/format/mypy strict
e diff check verdes. Tentativas anteriores e limites discriminados na evidência.
Etapa 8 concluída e local; Etapa 9 não iniciada.


## Encerramento da Etapa 9 — conferência final

O quadro abaixo é a conferência atual; os quadros de entregas anteriores são
históricos. Cada linha exige o gate final correspondente nesta rodada, além
dos testes específicos. Todos os gates desta rodada foram aprovados; os limites
documentados não foram ampliados. Evidência: [Etapa 9](PHASE-8-STAGE-9-VALIDATION.md).

| Requisito | Prova concreta e gate acumulado | Estado final |
|---|---|---|
| F8-001 | G-PKG: wheel/sdist instalados; installed_support.py e package.spec.js; mesma origem/processo em test_admin_ui_http.py | Aprovado |
| F8-002 | test_admin_ui_startup.py: test_exact_raw_flag, dependência UI/Admin e repr; fonte env/injetada | Aprovado |
| F8-003 | test_admin_ui_startup.py: falhas antes de todos os efeitos; installed_package_probe.py: dez recusas por pacote | Aprovado |
| F8-004 | test_admin_http_lifecycle.py, test_admin_http_mcp_coexistence.py; CLI instalada stdio/HTTP e restart | Aprovado |
| F8-005 | test_admin_ui_startup.py / admin_ui_compat_support.py; fixture literal off e test_admin_ui_startup.py | Aprovado |
| F8-006 | G-PKG; dependências/pins intactos; test_admin_ui_http.py e transport.spec.js: mesma origem sem CORS | Aprovado |
| F8-007 | test_phase8_final_inventory.py; commands.test.js; catálogo dez escritas; test_plan_separation.py | Aprovado |
| F8-008 | reading.spec.js: entrada/seis vistas/URL e history navigation; inventário integral | Aprovado |
| F8-009 | reading.spec.js: polling visible-only/serial/stops after failure e indisponibilidade | Aprovado |
| F8-010 | reader.test.js, reading.spec.js: snapshots divergentes, declarada/efetiva e readonly | Aprovado |
| F8-011 | author.test.js, batches.test.js; editing.spec.js e batches.spec.js: CRUD/reorder/restart reais | Aprovado |
| F8-012 | author.test.js, editing.spec.js; catálogo exato e preservação de exceptions em batches | Aprovado |
| F8-013 | author.test.js; editing.spec.js: eight editors, conditional integer e validação; test_admin_http_reads.py | Aprovado |
| F8-014 | batches.test.js / batches.spec.js: limites/tipos sem request e payload completo | Aprovado |
| F8-015 | batches.test.js / batches.spec.js: inclusão literal, Unicode/caixa e releitura autoritativa; efeito MCP | Aprovado |
| F8-016 | author.test.js, batches.test.js, editing.spec.js; test_admin_http_validate.py: candidata raiz sem efeitos | Aprovado |
| F8-017 | editing.spec.js: adoção/cancelamento/checkbox/backup/concorrência; test_admin_http_writes.py | Aprovado |
| F8-018 | commands.test.js, reader.test.js, protocol.test.js: versões inseguras e contraprovas de tipagem | Aprovado |
| F8-019 | coordinator.test.js / coordinator.spec.js: uma pendência/geração; editing e batches: abas/duplo clique/validação | Aprovado |
| F8-020 | coordinator.test.js, editing.spec.js, batches.spec.js: 409/busy/revisão explícita/edição externa | Aprovado |
| F8-021 | coordinator.test.js; editing/batches.spec.js: pre/post replace, perda/readback e auditoria; test_admin_service.py | Aprovado |
| F8-022 | reading/editing/batches.spec.js: API/PG, teclado/foco/320px/200%/reduced motion; limites de acessibilidade na evidência | Aprovado |
| F8-023 | protocol.test.js, test_admin_ui_resources.py, npm inspect e package.spec.js: 193 termos/literais | Aprovado |
| F8-024 | vocabulary.json inalterado; protocol.test.js: marcadores/encoding; D-062 e limite residual preservados | Aprovado |
| F8-025 | test_phase8_final_inventory.py e protocol.test.js: 19 calls, dez escritas, sete seções inteiras | Aprovado |
| F8-026 | protocol.test.js e test_admin_ui_resources.py: chaves estruturais/URLs/referências/ciclos; commands.test.js | Aprovado |
| F8-027 | protocol.test.js e test_admin_ui_resources.py: máximos inclusivos/estouro/DAG/catálogo; transporte bloqueado em metadata inválida | Aprovado |
| F8-028 | reading/lifecycle/editing.spec.js; coordinator.test.js: logout/401/eventos/retorno/respostas tardias; limite BFCache explícito | Aprovado |
| F8-029 | test_admin_ui_http.py: parser Host/origem, aliases/portas/IPv6/duplicados; transport.spec.js | Aprovado |
| F8-030 | test_admin_ui_http.py: Origin/Referer devem concordar e Fetch Metadata não é credencial | Aprovado |
| F8-031 | transport.test.js / transport.spec.js e commands.test.js: opções Fetch, destinos, redirects sem bearer | Aprovado |
| F8-032 | reading/editing/batches.spec.js: XSS persistido e outra sessão; transport.spec.js: controles positivos | Aprovado |
| F8-033 | Revisão §4.5, classes adversariais acumuladas e limites na evidência; nenhum finding novo de produto | Aprovado |
| F8-034 | transport/reading/lifecycle/editing.spec.js e commands.test.js: token sentinela/limpeza; reporter sanitizado e artefatos desativados | Aprovado |
| F8-035 | reader.test.js e reading.spec.js: secrets somente configured/missing; test_admin_http_leakage.py | Aprovado |
| F8-036 | commands/author/batches.test.js; editing/batches.spec.js e test_admin_adversarial.py: campos protegidos | Aprovado |
| F8-037 | test_plan_separation.py / test_purity.py; catálogo exato; installed_package_probe.py: MCP stdio | Aprovado |
| F8-038 | test_admin_ui_http.py::test_inventory_exact_twenty_or_twenty_four: igualdade 20/28 e 24/36 | Aprovado |
| F8-039 | test_admin_ui_http.py: produto cartesiano completo; package.spec.js: apresentação privada; nenhuma docs | Aprovado |
| F8-040 | test_admin_ui_http.py: test_precedence/test_media_type_before_routing; regressão BodyLimit da Fase 7 | Aprovado |
| F8-041 | test_admin_ui_http.py::test_http_product: queries vazia/x/token × rota/método/token | Aprovado |
| F8-042 | test_admin_ui_http.py: variantes raw_path, encoding, traversal e servidor real; transport.spec.js | Aprovado |
| F8-043 | test_admin_ui_http.py: métodos/preflight/recusas; transport.spec.js: CSRF/form/JSON real | Aprovado |
| F8-044 | test_admin_ui_http.py: Untouchable em toda matriz; browser_server.py compara zero efeitos/auditoria | Aprovado |
| F8-045 | test_admin_ui_http.py: bytes, erros e contenção; package.spec.js: bytes HTTP idênticos aos aprovados | Aprovado |
| F8-046 | test_admin_ui_http.py: HEAD/GET, Content-Length e erros precoces; servidor real | Aprovado |
| F8-047 | test_admin_ui_http.py: igualdade integral de headers/MIME; package.spec.js: MIME/no-store | Aprovado |
| F8-048 | test_admin_ui_http.py: CSP literal; transport.spec.js: CSP real e controles positivos | Aprovado |
| F8-049 | test_admin_ui_http.py: headers proibidos/Range/condicionais; fixture Fase 7 off | Aprovado |
| F8-050 | test_admin_ui_resources.py / test_admin_ui_startup.py; installed_package_probe.py: bytes reais/manifesto/âncora | Aprovado |
| F8-051 | Diff sem produto nesta etapa; test_plan_separation.py, test_purity.py e regressões completas da Fase 7 | Aprovado |
| F8-052 | npm ci/lock v3; package.json e browsers.json fixados; versões reais verificadas por scenario | Aprovado |
| F8-053 | checkJs strict/noEmit; protocol.test.js: 12 contraprovas de tipagem, sem escape novo | Aprovado |
| F8-054 | 14 hashes idênticos duas vezes e a HEAD; wheel/sdist externos; isolamento positivo e quatro contraprovas por pacote | Aprovado |
| F8-055 | 241 testes Node e 3830 Python coletados; gramática/contratos/limites/falhas acumulados | Aprovado |
| F8-056 | test_phase8_final_inventory.py: igualdade/21 contraprovas; test_admin_ui_resources.py e protocol.test.js: catálogos | Aprovado |
| F8-057 | npm inspect, protocol.test.js e package.spec.js: 193 termos nos bytes/literais públicos e contraprovas | Aprovado |
| F8-058 | coordinator/reading/editing/batches/lifecycle.spec.js: componentes reais em runner padrão; fixtures privadas | Aprovado |
| F8-059 | G-E2E instalado: Chromium 153.0.8010.12/1243, Firefox 155.0/1543, WebKit 26.6/2359; PostgreSQL 16.15 | Aprovado |
| F8-060 | test_admin_ui_http.py e transport/reading/editing/batches.spec.js: matriz adversarial de §6.7 | Aprovado |
| F8-061 | coordinator.test.js; browser_edit_server.py com editing/batches.spec.js; test_admin_adversarial.py: disco/digest/runtime/IDs/auditoria | Aprovado |
| F8-062 | Recibos desta Etapa 9: gates acumulados, oito skips POSIX, nenhum DSN ausente/deselect/xfail | Aprovado |
| F8-063 | Histórico de Etapas 1–8 aprovado/publicado sem emenda; Etapa 9 restrita a verificação; nenhum produto alterado | Aprovado |
| F8-064 | Quadro de aceite §7.2 na evidência; todos os gates finais devem passar antes do encerramento | Aprovado |
| F8-065 | batches.spec.js: flag bruta 0/1 e restart preservam bytes/backup/IDs/revision/MCP; matriz Python off Origin/Referer/headers | Aprovado |

Gates finais: 241 Node; 195/195 navegadores (65 por engine); nove E2E adicionais
do sdist; 3.830 Python coletados, 3.822 aprovados e oito skips POSIX, PostgreSQL
16.15 real. Instalação congelada, tipagem, dois builds idênticos, 193 termos,
pacotes isolados, Ruff, format, mypy strict e diff check aprovados. A primeira
matriz com um timeout permanece registrada, sem causa presumida.
