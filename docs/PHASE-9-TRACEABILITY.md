# Fase 9 — matriz de rastreabilidade normativa

**Estado:** Etapa 1 documental concluída e aprovada em 2026-09-22; Etapa 2
concluída; Etapa 3 (registry multi-datasource e lifecycle) implementada
localmente em 2026-09-23, ativada somente pelo composition root (D-087). A
Etapa 4 (Admin API v2 de datasources) foi autorizada e implementada localmente
em 2026-09-24, sem push (D-092–D-096); UI v2, PGWire e as Etapas 5–12
continuam não iniciados.

**Fonte normativa:** [PHASE-9-SPEC.md](PHASE-9-SPEC.md). A matriz cobre todas
as Etapas 2–12 e distingue requisito, etapa responsável, prova obrigatória e
estado atual. “Planejada” não é evidência de execução: cada etapa só pode ser
fechada com os artefatos e números medidos no seu próprio registro de validação.

## Requisitos e evidência verificável

| ID | Requisito normativo | Seções | Etapa(s) | Evidência obrigatória | Estado |
|---|---|---:|---:|---|---|
| F9-001 | IDE usa host/port/dbname/user/password do Gateway | 1, 4.1–4.2 | 7–10 | conexão real nos quatro clientes certificados, sem conexão direta ao destino | planejada |
| F9-002 | MCP permanece e compartilha o pipeline seguro | 2, 10–11 | 3, 8, 11 | paridade de masking, read-only, timeout e erros entre MCP e PGWire | Etapa 3: sessões de datasource usam o mesmo `execute_validated` e `run_audited` do MCP, provado contra PostgreSQL 16; paridade com PGWire pendente (8, 11) |
| F9-003 | Somente SELECT, com defesa também no PostgreSQL | 2, 5.4, 12 | 3, 8–10 | validator, sessão read-only, tentativas de escrita e funções perigosas | Etapa 3: cada sessão verifica read-only/timeout/proveniência; escrita recusada pelo validator e pelo PostgreSQL; PGWire pendente (8–10) |
| F9-004 | Alias fechado resolve datasource, nunca destino informado pelo cliente | 4.1, 6.1 | 2–4, 7 | aliases inválidos, desconhecidos, desabilitados e enumeração bloqueados | Etapa 4: alias validado no schema, imutável (`IMMUTABLE_FIELD`), conflito sem ecoar o alias, destino só por campos administrativos; PGWire pendente (7) |
| F9-005 | Autenticação Gateway separada da upstream | 4.2–4.3, 5.3 | 2, 7 | SCRAM-SHA-256, proof não reutilizável, credencial upstream nunca retornada | planejada |
| F9-006 | Um principal operacional; sem RBAC implícito | 4.2, 8–9 | 4, 6, 7 | inventário fechado de identidades e ausência de autorização por alias | Etapa 4: a v2 usa o mesmo token administrativo, sem identidade nova nem autorização por alias; UI e PGWire pendentes (6, 7) |
| F9-007 | TLS obrigatório fora de loopback | 5.1–5.2 | 7 | bind externo, SSLRequest, downgrade, certificado/chave inválidos | planejada |
| F9-008 | Settings PGWire estritos e opt-in | 5.1, 11 | 7 | matriz de valores brutos; falhas antes de bind, store e MCP | planejada |
| F9-009 | Simple query no subconjunto seguro | 5.3–5.5 | 8 | psql/psycopg, framing adversarial, masking e CommandComplete | planejada |
| F9-010 | Extended query e parâmetros por sessão | 5.3–5.4 | 9 | Parse/Bind/Describe/Execute/Close/Sync, JDBC e prepared statements | planejada |
| F9-011 | Cancelamento isolado por sessão | 5.3, 7, 12 | 9 | CancelRequest válido, inválido e cruzado, sem enumeração | planejada |
| F9-012 | Catálogo mínimo de IDE sem allowlist genérica | 5.4, 12 | 10 | snapshots das queries dos quatro clientes e contraprovas de bypass | planejada |
| F9-013 | Protocolo/formato não suportado falha fechado | 5.3–5.5, 12 | 7–10 | frames malformados, máquina de estados, tamanhos e UTF-8 | planejada |
| F9-014 | Tipos/metadados não expõem proveniência | 5.5, 13 | 8–10 | RowDescription, OID/typmod, NULL, duplicatas e colunas mascaradas como texto | planejada |
| F9-015 | Limite de linhas observável sem dado extra | 5.5, 14.2 | 8 | NOTICE fixo, linha N+1 descartada antes de masking e sem leakage | planejada |
| F9-016 | Catálogo persistente multi-datasource, fechado e autenticado | 6.1–6.2 | 2 | roundtrip, schema, metadata tamper, truncamento e integridade | implementada na Etapa 2; evidência local |
| F9-017 | Segredo upstream write-only e cifrado por AEAD | 4.3, 6.2, 13 | 2, 4, 6 | AES-256-GCM, nonce único, tamper, transplant e canários de leakage | implementada na Etapa 2; evidência local |
| F9-018 | Chave-mestra externa e rotação explícita | 5.1, 6.2 | 2, 12 | chave ausente/errada, rotação, ausência de fallback e nenhum plaintext | implementada na Etapa 2; evidência local |
| F9-019 | Migração do DSN único explícita e reversível | 6.3, 10, 17 | 2, 11 | importação, restart, desligamento explícito e retorno real ao legado | migração explícita implementada; rollback/runtime pendentes |
| F9-020 | Registry por alias/generation com refcount | 7, 11 | 3 | concorrência, fechamento único, aposentadoria e isolamento | implementada na Etapa 3; evidência local |
| F9-021 | Conexão upstream por sessão e limites | 5.1, 7, 11–12 | 3, 7–10 | sessões máximas, por-datasource, idle, slow clients e cleanup | Etapa 3: conexão por sessão, limites globais/por datasource e cleanup implementados; idle e slow clients pendentes (7–10) |
| F9-022 | Candidato testado antes de persistir/publicar | 6.3, 7–8 | 2–4 | falhas de conexão/capability sem efeito em bytes, runtime ou revision | Etapas 3–4: coordenador e rotas v2 provados, inclusive contra PostgreSQL 16 real |
| F9-023 | Datasource habilitado inválido falha startup | 7, 11 | 2–3 | subprocesso com zero Admin HTTP, PGWire ou MCP publicados | implementada na Etapa 3 pelo composition root (D-087); ativação por settings de processo pendente (7) |
| F9-024 | Admin API v2 não quebra v1 | 8, 11 | 4 | inventário v1 imutável, v2 fechado e regressão byte a byte | implementada na Etapa 4: inventários literais, comparação sonda a sonda com e sem v2, v1 sem importar a v2 |
| F9-025 | Concorrência otimista por datasource | 6.1, 8 | 4, 6 | revision, conflito, busy, durability e uma publicação por vencedor | Etapa 4: revision por datasource sob o lock, um vencedor por revision, busy, falha certa/incerta; UI pendente (6) |
| F9-026 | Teste de conexão não publica runtime | 2, 7–8 | 4, 6 | identidade, digest, revision, arquivo e registry inalterados | Etapa 4: rascunho e persistido sem efeito em bytes, revisions, `last_test`, registry e candidatos; UI pendente (6) |
| F9-027 | UI não executa SQL nem mostra resultados | 3.1, 8–9 | 5–6, 12 | inventário, AST, rede e chamadas fechadas; contraprovas positivas | planejada |
| F9-028 | UX v2 possui dashboard, lista, wizard e detalhe | 9 | 5–6 | screenshots aprovados, E2E e estados de erro/concorrência | planejada |
| F9-029 | Token, segredos e drafts continuam voláteis | 4.1, 9.1–9.3 | 5–6 | lifecycle, BFCache, storage, URL, DOM, logs e leakage | planejada |
| F9-030 | Acessibilidade em 320 px, 200% e reduced motion | 9.2, 14 | 5–6 | três browsers, teclado/foco e revisão manual registrada | planejada |
| F9-031 | Nenhuma dependência ou recurso externo na UI | 9.2–9.3, 14 | 5–6, 12 | CSP, rede, pacote instalado e inventário de dependências | planejada |
| F9-032 | MCP aceita alias opcional sem quebrar `sql` | 10 | 11 | clientes antigos, novo cliente e default explícito | planejada |
| F9-033 | MCP não enumera aliases nem altera catálogo | 10 | 11 | schema/tool único, erros fixos e AST de separação de planos | planejada |
| F9-034 | SSRF e DNS rebinding no destino são bloqueados | 6.1, 12 | 2, 4, 12 | loopback, link-local, multicast, metadata cloud e resolução mutável | Etapa 4: destinos proibidos e DNS trocado recusados pelas rotas, sem ecoar o destino; resolução com prazo (D-092); revisão final pendente (12) |
| F9-035 | Nenhuma informação sensível em observabilidade | 2, 6.2, 13 | 2–12 | canários de senhas, chave, SQL, destino, ciphertext, nonce e célula | redaction da Etapa 2 implementada; cobertura futura pendente |
| F9-036 | Lifecycle ordenado das três fronteiras | 11 | 3–12 | falha em cada passo, bind confirmado, drain e shutdown sem órfãos; limite DNS antes da Admin v2; limite da verificação pós-conexão de candidatos antes da ativação da v2 pelo operador (7); limite de validação/masking locais antes de novo ingresso SQL (8, 11); nada abandonado | Etapas 3–4: passos 3–7 da §11, drain, shutdown e limite efetivo de DNS (D-092, shutdown com resolução em voo provado). **Em aberto:** verificação pós-conexão de candidatos sem teto do lado do cliente (gate da Etapa 7) e validação/masking locais (gates das Etapas 8 e 11) |
| F9-037 | Riscos F-01 a F-11 não regridem | 2, 5, 12 | 8–12 | suíte de segurança completa por datasource e função/catálogo | planejada |
| F9-038 | Pacote instalado funciona sem checkout/Node | 14 | 12 | wheel e sdist isolados, sem fallback ao checkout ou Node | planejada |
| F9-039 | Rollback volta ao modo legado sem fallback silencioso | 6.3, 10–11, 17 | 11–12 | restart com PGWire/store desligados e MCP legado funcionando | planejada |
| F9-040 | Compatibilidade declarada é certificada, não universal | 5.3, 14 | 10, 12 | versões fixadas, tabela de suporte e recusa fora do subconjunto | planejada |

## Cobertura por etapa

| Etapa | Entrega normativa | IDs principais | Gate de saída verificável | Estado |
|---:|---|---|---|---|
| 2 | modelo, store autenticado/cifrado e migração | F9-016–019, F9-022–023, F9-034–035 | testes AEAD/metadata, âncora de replay, atomicidade, SSRF, leakage e subprocesso fail-closed | concluída; F9-022–023 integrados na Etapa 3 |
| 3 | registry multi-datasource e lifecycle | F9-002–003, F9-020–023, F9-036 | concorrência, generations, refcount, drain, fechamento único e isolamento | implementada localmente; evidência em `PHASE-9-STAGE-3-VALIDATION.md` |
| 4 | Admin API v2 de datasources | F9-004–006, F9-022, F9-024–026, F9-034, F9-036 | auth/CSRF, revisões, teste sem publicação, v1 intacta, destino validado e resolução DNS com limite efetivo | implementada localmente em 2026-09-24, sem push; evidência em `PHASE-9-STAGE-4-VALIDATION.md` |
| 5 | UX v2 somente leitura | F9-027–031 | screenshots, a11y, token/draft lifecycle, CSP e três browsers fixados | não iniciada |
| 6 | CRUD visual de datasources e policies | F9-016–019, F9-025–031, F9-035 | segredo write-only, rotação, concorrência, confirmação destrutiva e sem SQL/resultados | não iniciada |
| 7 | PGWire startup, TLS e autenticação | F9-001, F9-005–008, F9-011, F9-013, F9-021, F9-036 | harness binário, SCRAM, TLS externo, limites, erro sanitizado e lifecycle; limite efetivo da verificação pós-conexão de candidatos antes de ativar a Admin v2 pelo operador, sem abandonar thread, processo ou conexão | não iniciada |
| 8 | simple query e masking | F9-002–003, F9-009, F9-014–015, F9-036–037 | psql/psycopg, PostgreSQL 16 real, SELECT-only, masking, truncamento e limite efetivo do processamento local | não iniciada |
| 9 | extended query, parâmetros e cancelamento | F9-010–011, F9-013–015, F9-021, F9-036–037 | JDBC/prepared statements, Sync, formatos, CancelRequest e isolamento | não iniciada |
| 10 | catálogo seguro e quatro IDEs | F9-001, F9-012–015, F9-040 | navegação real, snapshots fechados, tipos e matriz certificada | não iniciada |
| 11 | MCP multi-datasource e migração legada | F9-002, F9-004, F9-019, F9-032–033, F9-036, F9-039 | clientes antigos, alias/default, rollback real, zero enumeração/configuração e limite do processamento local antes do novo ingresso | não iniciada |
| 12 | pacote, revisão adversarial e fechamento | F9-007, F9-018, F9-027–031, F9-034–040 | wheel/sdist, todos os gates, canários de leakage, browsers e critérios da §17 | não iniciada |

## Rastreabilidade das decisões D-065–D-076

| Decisão | Tema | Seções normativas | Etapas que provam |
|---|---|---|---:|
| D-065 | façade segura, não proxy | 1–2, 5.3–5.5, 7, 12 | 7–10 |
| D-066 | alias em `dbname` | 4.1, 6.1, 7, 10 | 2–4, 7, 11 |
| D-067 | identidades separadas/SCRAM | 4.2–4.3, 5.3, 12 | 2, 6, 7 |
| D-068 | principal único, sem RBAC | 4.2, 8–9 | 4, 6, 7 |
| D-069 | AEAD, catálogo autenticado e replay | 6.1–6.3, 12–13 | 2, 6, 12 |
| D-070 | TLS fora de loopback | 5.1–5.3, 8, 11 | 7, 12 |
| D-071 | conexão por sessão | 7, 11–12 | 3, 7–10 |
| D-072 | clientes certificados | 5.3–5.5, 14 | 7–10, 12 |
| D-073 | UX v2 segura/local | 2, 8–9, 12–14 | 4–6, 12 |
| D-074 | MCP stdio e alias posterior | 2, 10–11 | 8, 11–12 |
| D-075 | rollback legado explícito | 6.3, 10–11, 17 | 2, 11–12 |
| D-076 | fail-closed no startup | 5–8, 11–14 | 2–4, 7, 12 |

## Rastreabilidade das decisões de implementação D-077–D-086

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-077 | `cryptography==50.0.1`, AESGCM/HKDF/HMAC | `src/maskgw/datasource/crypto.py`; validação de dependência |
| D-078 | JSON canônico, schema fechado, digest SHA-256 | `crypto.py`, `store.py`; roundtrip/tamper |
| D-079 | envelope v1, nonce de 12 bytes e AAD por ID/campo/revision | `crypto.py`; cifra, rotação e chave errada |
| D-080 | âncora em diretório separado, sem arquivo comum confiável | `store.py`; replay/transplant e filesystem |
| D-081 | journal old/new e recuperação old/old, new/old, new/new decidida antes de qualquer escrita; erro pós-replace incerto | `store.py`; pontos de crash de escrita, inicialização e rotação; abertura com chave errada sem escrita |
| D-082 | rotação explícita sem fallback; determinação e recuperação explícitas com as duas chaves; conclusão só após remover backups da chave anterior | `CatalogStore.rotate_master_key`, `inspect_master_key_rotation`, `recover_master_key_rotation`; sete limites de crash × chave antiga/nova/errada, idempotência e chaves inválidas |
| D-083 | locks, temporários, backups, replace, fsync e limpeza seletiva; remoção verificada dos backups após o commit da rotação | `store.py`; testes de lock/recuperação, falha/retomada da remoção, remoção sem efeito, nomes desconhecidos, diretórios e symlinks |
| D-084 | validação SSRF e conjunto DNS fixado | `destination.py`; metadata e rebinding |
| D-085 | ausência, corrupção e chave inválida falham fechadas | `CatalogStore.open`; testes de tamper/anchor/key |
| D-086 | migração DSN explícita, em memória e não destrutiva | `migration.py`; teste byte a byte do legado |

## Rastreabilidade das decisões da Etapa 3 D-087–D-091

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-087 | `build_application(datasource_catalog=...)`; import tardio do catálogo | `test_datasource_bootstrap.py`: legado sem módulo de catálogo, ordem de startup, subprocesso fail-closed |
| D-088 | `effective_database_settings` (mínimo entre policy e limits) | `test_datasource_runtime_service.py` |
| D-089 | `DatasourceRegistry`, `DatasourceGeneration`, `DatasourceLease`, reservas | `test_datasource_registry.py`: gerações, limites, isolamento e concorrência |
| D-090 | shutdown em duas fases, `PostgresAdapter.cancel` | `test_datasource_registry.py`, `test_datasource_bootstrap.py` e cancelamento real em `test_datasource_runtime_integration.py` |
| D-091 | `DatasourceRuntimeService`, `build_candidate` | `test_datasource_runtime_service.py` e `test_datasource_runtime_integration.py` |

## Rastreabilidade das decisões da Etapa 4 D-092–D-096

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-092 | `maskgw/datasource/resolver.py`, default de `resolve_destination` | `test_datasource_resolver.py`, shutdown com DNS lento em `test_admin_v2_lifecycle.py`, integração real |
| D-093 | `maskgw/admin/http/v2/`, `build_router(datasources=...)`, `_build_admin_http` | `test_admin_v2_http.py`: inventário, v1 byte a byte, fronteira, schema fechado e leituras sem segredo |
| D-094 | `DatasourceRuntimeService`: revision por datasource, mutação/confirmação sob lock, probe, teste de desabilitado, política compilada | `test_datasource_service_v2.py`, `test_admin_v2_concurrency.py`, `test_admin_v2_http.py` |
| D-095 | `admin/http/v2/errors.py`, `audit/datasource.py`, `AuditLog.record_datasource_admin` | `test_admin_v2_audit.py` e auditoria nos testes HTTP |
| D-096 | ausência da rota de default do MCP | inventário literal em `test_admin_v2_http.py` |

## Gates comuns e limites desta matriz

- PostgreSQL 16 real em todos os gates de integração; `MASKGW_TEST_DSN` deve
  ser usado sem imprimir seu conteúdo, e nenhum skip por ausência de DSN é
  aceitável.
- Ruff, format check, mypy strict, `git diff --check`, Node/checkJs, testes
  Node, builds determinísticos e browsers fixados entram somente nas etapas em
  que a especificação os exige; suas versões e resultados devem ser medidos,
  não herdados de evidência histórica.
- No Windows, a suíte Python usa a pilha de thread de 64 MiB já documentada;
  o teste adversarial não pode ser deselected, skipped ou xfailed.
- Nenhum finding pode virar skip/xfail. Skips exclusivamente de plataforma
  devem ser separados e explicados na evidência da etapa.
- A matriz não autoriza as Etapas 4–12. A evidência executável das Etapas 2 e
  3 está em `docs/PHASE-9-STAGE-2-VALIDATION.md` e
  `docs/PHASE-9-STAGE-3-VALIDATION.md`; os resultados históricos da Fase 8
  continuam exclusivamente em sua própria evidência e não são reatribuídos.
