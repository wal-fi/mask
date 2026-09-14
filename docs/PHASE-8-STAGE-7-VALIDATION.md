# Fase 8 — Evidência da Etapa 7

**Estado:** Etapa 7 concluída; todos os gates finais aprovados.
**Data:** 2026-09-14. **Escopo:** adoção legada, validação explícita e CRUD
granular de regras/exceptions, usando os contratos das Etapas 2–6.

## Checkpoint e publicação da Etapa 6

Confirmados master, HEAD `db33fa770e1b675ee23ad554a84c93a7e9e2f358`,
origin/master `0d42f5d0d9a835177dd1c5e4a6c608161f585896`, árvore limpa e
1 ahead / 0 behind. Autor e committer `w.filho <w.filho@live.com>`;
trailer `Co-Authored-By: Codex <noreply@openai.com>`.

Foi publicado exatamente `db33fa770e1b675ee23ad554a84c93a7e9e2f358`, sem amend,
rebase ou alteração de arquivo. O fetch confirmou HEAD igual a origin/master,
0/0 e árvore limpa, com identidade e trailer preservados. Esta rodada não
publica a Etapa 7 e não autoriza nem inicia a Etapa 8.

## Integração e contratos funcionais

`author.js` interpreta exclusivamente os modelos/controles privados autenticados.
Deriva dois perfis CRUD: regras e exceptions. Não recebe URL, método, expressão
ou campo arbitrário. `workbench.js` conecta esses perfis ao coordenador e ao
transporte existentes. `release` limpa um coordenador sem fechar o transporte,
permitindo encerrar um diálogo e iniciar outra edição explícita na mesma sessão.

Uma edição conserva snapshot-base/revision-base e rascunho. Valores inválidos
permanecem no formulário sem produzir requests; corpos válidos são copiados e
congelados antes da confirmação. Polling da tela fica suspenso durante toda
edição, inclusive validação. Uma única escrita por aba; nenhum autosave, fila,
retry, rebase ou rollback automático. Os demais botões não admitem outra
operação enquanto a atual está pendente.

| Ação visível | Contrato existente usado |
|---|---|
| Validar documento/proposta | POST /admin/v1/config:validate; candidato raiz, sem expected_revision |
| Adotar configuração | POST /admin/v1/config:adopt; expected_revision 0 e confirm_comment_loss true |
| Criar regra | POST /admin/v1/rules; conteúdo completo e versão-base, append pelo backend |
| Editar regra | PUT /admin/v1/rules/{rule_id}; conteúdo completo, preservando identidade/posição |
| Excluir regra | DELETE /admin/v1/rules/{rule_id}; confirmação explícita e versão-base |
| Criar exception | POST /admin/v1/exceptions; conteúdo completo, append e confirmação |
| Editar exception | PUT /admin/v1/exceptions/{exception_id}; posição preservada e confirmação |
| Excluir exception | DELETE /admin/v1/exceptions/{exception_id}; confirmação e somente alvo |

O catálogo ainda contém as dez escritas normativas, mas os controles desta
etapa expõem somente adoção e as seis operações CRUD. Reorder e edição de
database/SQL continuam ausentes. Nenhum PUT /config ou chamada MCP pela UI.
IDs, posições, revision e allowed_pg_functions não são campos editáveis.

Regras começam com contains/case_sensitive=false; exceptions começam com
exact/case_sensitive=false. Match é preservado literalmente, inclusive espaços.
Transformer exige escolha explícita. O registry autenticado é confrontado com
os oito editores privados e seus parâmetros. Campos extras/secretos são
recusados; inteiros não aceitam booleanos, frações ou coerções silenciosas.
Random remove length quando preserve_length=true; length zero é válido quando
aplicável. Transformer desconhecido/incompatível fica visível na leitura e
bloqueia edição, preservando conteúdo. Não há execução regex ou preview no JS.
As orientações de risco de hashes, truncate, random e exceptions vêm do privado.
Toda edição de exception pede confirmação, conservadoramente inclusive quando
não amplia a correspondência; o aviso explica valor original e nome autoritativo.

Legado permite leitura e validação, mas CRUD fica desabilitado. O diálogo de
adoção explica IDs, revision 1, perda possível de comentários/formatação,
backup do backend e ausência de alteração intencional da política. Checkbox
começa falso; somente o gesto final “Adotar configuração” envia a operação.
Cancelamento/falso não fazem request; backup nunca é mostrado. Sucesso exige
releitura e usa somente as identidades recebidas do servidor.

## Validação transitória

A projeção parte da base completa e do rascunho verificado, conservando os
valores protegidos de database/SQL. Remove IDs/revision na cópia transitória,
nunca na base; não envia envelope GET ou expected_revision. O leitor foi
corrigido para não considerar dois IDs opcionais ausentes como duplicados.
IDs obrigatórios nas leituras e duplicatas presentes continuam recusados.

A resposta positiva exige exatamente valid=true, schema_validated=true,
policy_compiled=true e database_checks_performed=false, sem campos extras.
A restrição é do modelo privado da UI; os schemas Python não foram alterados.
Alteração do rascunho/base invalida a prova, aborta a espera e descarta resposta
antiga. A mensagem distingue conteúdo/compilação de salvamento, conexão e
proteção integral. Reasons só se associam a paths exatos dos controles conhecidos,
com texto privado fixo e aria-describedby. Detail e paths inesperados não são
mostrados. A validação não muda arquivo, snapshot, digest ou contador de escrita;
produz apenas o evento validate já previsto no backend.

## Concorrência, recuperação e segurança

Sucesso exige applied e próxima revision coerentes, seguido de releitura. Sem
releitura, informa “Salva; visualização ainda não atualizada”. Conflito mantém
rascunho/base original e mostra nova base separada; revisão humana é explícita.
Busy só admite tentativa manual. Resultado desconhecido, incompatibilidade e
durabilidade incerta bloqueiam novas escritas na sessão, inclusive depois de
fechar/descartar o diálogo. Revision maior não atribui autoria nem libera retry.
Não há desfazimento automático de arquivo, IDs, revision ou runtime publicados.

Formulários e diálogos são semânticos, com labels, heading, anúncios de estado,
Tab contido/restaurado e escolha descartar/continuar. Reconstruir campos
condicionais restaura o foco no controle correspondente. Cancelar/navigation
com rascunho alterado exige descarte explícito. Há provas a 320 px, escala 200%
e reduced motion. Nenhum dado administrativo vai para URL/histórico, data-attrs,
stores, logs ou artefatos do runner. Entradas usam propriedades transitórias;
valores remotos são sempre texto, nunca HTML dinâmico.

Token continua somente na closure privada do transporte e no Authorization
necessário ao request. Corpo e reflexão são verificados inclusive com escapes
JSON. Logout/401/pagehide/pageshow limpam token, rascunho, base, metadados e DOM,
incluindo diálogo de descarte aninhado, e invalidam tickets. Callbacks antigos
não reconstroem estado. Nenhum script/fonte/asset externo, armazenamento, telemetria
ou dependência nova. As políticas HTTP/CSP/origem/Host/proxy da Etapa 4 e a
fixture UI off permanecem intactas. D-061–D-064 permanecem vigentes.

## Provas reais e limites da instrumentação

O novo `tests/browser_edit_server.py` usa composition root e PostgreSQL reais.
Instrumenta requests no harness, sem rota ou opção de produto. Para cada escrita,
confere corpo, versão, operação/alvo/outcome/revisions do AdminAudit e estado
persistido. O monitor também recusa token/DSN nos logs e warnings inesperados.
`test_browser_edit_harness.py` testa esse monitor e seus casos negativos.

Os casos de browser verificam adoção cancelada/falsa/concorrente, backup original,
validação sem efeito, CRUD completo, match literal, defaults, mudanças de campos,
confirmações, duplo clique, abas concorrentes, busy, XSS persistido, reasons
hostis, lifecycle, releitura falha e resposta perdida. O fluxo real
HTTP → runtime → MCP prova que a regra aplicada produz masking; o SQL da prova
existe somente no teste privado e não vira tela, endpoint ou expansão MCP.
Restart confirma o arquivo persistido e o snapshot administrativo.

Falhas privadas por stdin: pre recusa antes de write_atomic; reload recusa
construção do adapter antes de publicar; durability executa a escrita real e
então lança ConfigDurabilityError com o digest resultante. Esta última prova
**não** é um fsync de diretório POSIX nativo em Windows. Busy usa lease real do
runtime aposentado. Resposta perdida é abortada no browser depois de route.fetch
ter efetuado o commit real. Há inspeção de disco/runtime/auditoria após o desfecho,
sem retry e sem aumentar o escopo HTTP. Os testes componentes de estados da
Etapa 6 continuam acumulados e não substituem essas provas reais.

BFCache nativo adicional permanece comprovado em Chromium pelo controle já
aprovado. Firefox/WebKit têm eventos persisted, navegação/reload e cleanup;
Playwright não acompanha restauração nativa nesses engines. Não alegar prova
mais ampla. Limpeza remove referências controladas pela aplicação, sem promessa
de sobrescrever heap ou proteger contra navegador/extensão/processo comprometido.
O fechamento operacional final e a revisão transversal da Etapa 9 permanecem
futuros; rollback continua flag/restart e não desfaz configuração persistida.

Findings corrigidos antes dos gates: IDs transitórios ausentes tratados como
duplicatas, colisão de nome no ESM, default privado incompatível com o const da
adoção, comparação de enums serializados no monitor de audit, encerramento do
harness antes de remover o diretório Windows e perda de foco ao reconstruir
campos condicionais. Nenhum finding virou skip/xfail ou exceção lexical.
Rodadas preliminares não contam como medições finais. Ruff permanece src tests;
os diagnósticos históricos dos geradores privados fora desse gate não são
apresentados como resolvidos.

## Falha observada na primeira execução Python

A primeira suíte completa coletou 3808 casos: 3799 aprovados, uma falha e oito
skips POSIX (585,47 s de processo; JUnit 568,735 s). O caso existente
`TestSessaoMcpComAdminAtivo.test_uma_sessao_mcp_real_nao_ve_byte_estranho_em_stdout`
falhou com Connection closed durante session.initialize. O stderr preservado
do subprocesso continha exatamente a mensagem genérica de inicialização,
sem traceback ou conteúdo administrativo. Nenhuma causa específica foi
comprovada por essa saída; não atribuir silenciosamente a carga, porta ou rede.

A repetição diagnóstica do arquivo `test_admin_http_mcp_coexistence.py` passou
os seis testes com PostgreSQL 16.15 real em 141,34 s, sem mudanças no produto,
no teste, em timeout ou em marcações. Ruff/format/mypy também passaram nesse
diagnóstico. Isso não substitui o gate completo, repetido integralmente e
registrado abaixo. Nenhum finding foi convertido em skip/xfail. A ocorrência
inicial permanece registrada como falha de startup não reproduzida no diagnóstico.

## Reprodução e ferramentas

Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e @types/node
24.0.0; lock npm v3 e pins preservados, nenhuma instalação/atualização de browser.
Executar em frontend: npm ci --ignore-scripts, npm run build duas vezes,
comparar os 14 outputs, npm run typecheck, npm run inspect e npm test.
O build confere sintaxe ESM, checkJs strict/noEmit e bytes públicos finais.

Com MASKGW_TEST_DSN em PostgreSQL 16 real, executar npm run test:browser, sem
filtros, retries ou traces. Nesta rodada os launchers usam postgres:16-alpine
local com --pull never, porta aleatória exclusiva em 127.0.0.1 e credencial
aleatória somente em memória/ambiente; removem container/volume no finally.
Chromium 153.0.8010.12 (1243), Firefox 155.0 (1543), WebKit 26.6 (2359).

Suíte Python inteira: pytest.main(['-q', '-ra', '--junitxml=...']) em thread
com threading.stack_size(64 * 1024 * 1024), join e propagação do exit code.
O ajuste é temporário do launcher Windows, sem alterar produto/testes (D-041).
Sem deselect/filtro ou skip por DSN. Rodar Ruff check, Ruff format --check e
mypy --strict em src tests e git diff --check sobre worktree/índice.

Python 3.11.3; pytest 9.1.1, ruff 0.16.5, mypy 2.3.1, pydantic 2.13.5,
psycopg 3.3.4, fastapi 0.141.1, uvicorn 0.52.4 e mcp 2.1.1, medidos novamente.
Construir wheel/sdist com setuptools.build_meta; setuptools 68.2.2,
wheel 0.45.1 e packaging 24.2. Instalar cada um fora do checkout com
--no-index --no-deps --no-build-isolation --no-compile. Python -I -S importa
do target, com dependências existentes e PATH somente do sistema; verificar
quatro recursos e igualdade dos bytes, sem Node/npm. Nenhum frontend, fixture,
teste, sourcemap ou tipo privado no pacote.

## Recursos e distribuição

Oito dos 14 outputs mudaram: apresentação privada/final, nomes de modelos,
catálogo gerado, JS, CSS, manifesto e âncora. HTML, gramática, contratos e
vocabulário estão iguais ao commit aprovado da Etapa 6. Nenhum recurso novo.
110 modelos, 19 chamadas, 44 controles, seis vistas e oito editores; todos os
limites normativos preservados. Inspeção de 193 termos privados sem exceção nova.

| Recurso | Bytes UTF-8 | SHA-256 |
|---|---:|---|
| index.html | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| ui.js | 102229 | `c67ef6725a3ca50dee2f2d03101fe7a3efbcda1be632dc9f9da389eb97f9942c` |
| ui.css | 1606 | `3e497e58fbe81bb417342a1d87bed03bfa50e0c6501f43a89cd805485f16482f` |
| presentation.json | 38802 | `58667c237b89912f66bd035457778be0bcb11ba730d44cefcca22fe5405f2825` |

SHA-256 do manifesto interno: `af1e5010d5240f5ad045a9b013d5b105d5ffbef5edfa95f648d998f0051c235b`.

| Pacote medido | Entradas | Bytes | SHA-256 |
|---|---:|---:|---|
| maskgw-0.1.0-py3-none-any.whl | 81 | 201152 | `8c6c550fbab279937ad8ffda12f723c0bd68024260a1dc955955a315d14a5066` |
| maskgw-0.1.0.tar.gz | 104 | 170101 | `f881305992cf0fb0e77f0e25d2ac1f7f3298eb57e19097597958aba4914dc123` |

Cada instalação isolada validou quatro recursos e os mesmos bytes do checkout.
Os hashes dos arquivos compactados identificam esta execução; timestamps de
empacotamento não são tratados como build reproduzível de wheel/sdist.

## Medições finais

| Gate | Resultado medido | Tempo de processo |
|---|---|---:|
| npm ci --ignore-scripts | Instalação congelada, exit 0 | 5,84 s |
| Build 1 | Exit 0, sintaxe ESM e tipagem incluídas | 29,22 s |
| Build 2 | 14 outputs idênticos, LF | 22,08 s |
| Typecheck | checkJs strict/noEmit, sem supressões | 5,72 s |
| Inspeção pública | 193 termos e contraprovas aprovados | 1,23 s |
| Node | 195 aprovados, zero falhas/skips/cancelamentos | 338,70 s |
| Playwright | 156 aprovados, 52 por engine; zero falhas/skips/retries | 1630,03 s |
| Python completo | 3808 coletados, 3800 aprovados, oito skips POSIX | 541,66 s |
| Ruff check src tests | Exit 0 | 0,61 s |
| Ruff format --check src tests | 137 arquivos, exit 0 | 0,39 s |
| mypy --strict src tests | 137 arquivos, exit 0 | 2,22 s |
| Wheel/sdist | Instalação isolada e quatro recursos válidos, sem Node/npm | 37,89 s |
| git diff --check | Worktree e índice conferidos antes do commit | Sem cronometragem |

Node: 337970,8609 ms internos. JUnit Python: 533,545 s, início
2026-09-14T14:44:16.773618-03:00. PostgreSQL 16.15 real, sem filtro/deselect ou
skip por ausência de MASKGW_TEST_DSN. A repetição integral passou; o diagnóstico
isolado de seis casos não foi contado como substituto nem somado a esse total.
O warning preexistente de pytest sobre match="" continua sem silenciamento.

Os oito skips medidos são exclusivamente de plataforma: cinco fsync de
diretório e três bits de modo POSIX. Casos do JUnit final:

- `tests.test_admin_adversarial.TestLeakageNasFalhasDeEscrita.test_durability_error_depois_do_replace_nao_vaza`;
- `tests.test_admin_http_audit.TestDurabilidade.test_durability_error_publica_com_revision_after`;
- `tests.test_admin_http_writes.TestDurabilidade.test_fsync_de_diretorio_falho_publica_com_applied_true`;
- `tests.test_admin_service.TestDurability.test_real_directory_fsync_failure_is_post_commit_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_group_writable_config_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_world_writable_parent_is_rejected_on_posix`;
- `tests.test_config_filesystem.TestValidation.test_reused_lock_must_be_mode_0600_on_posix`;
- `tests.test_config_filesystem.TestDurability.test_directory_fsync_failure_is_post_commit`;

## Arquivos desta entrega

- `AGENTS.md`;
- `CLAUDE.md`;
- `docs/ARCHITECTURE.md`;
- `docs/HANDOFF.md`;
- `docs/PHASE-8-SPEC.md`;
- `docs/PHASE-8-STAGE-7-VALIDATION.md`;
- `docs/PHASE-8-TRACEABILITY.md`;
- `docs/ROADMAP.md`;
- `docs/SECURITY.md`;
- `docs/TEST-PLAN.md`;
- `frontend/README.md`;
- `frontend/browser/editing.spec.js`;
- `frontend/browser/harness.js`;
- `frontend/private/model-names.json`;
- `frontend/private/presentation.json`;
- `frontend/src/author.js`;
- `frontend/src/coordinator.js`;
- `frontend/src/reader.js`;
- `frontend/src/screen.js`;
- `frontend/src/transport.js`;
- `frontend/src/workbench.js`;
- `frontend/test/author.test.js`;
- `frontend/tools/build.js`;
- `frontend/tools/presentation.py`;
- `src/maskgw/admin/ui/_anchor.py`;
- `src/maskgw/admin/ui/_catalog.py`;
- `src/maskgw/admin/ui/assets/manifest.json`;
- `src/maskgw/admin/ui/assets/presentation.json`;
- `src/maskgw/admin/ui/assets/ui.css`;
- `src/maskgw/admin/ui/assets/ui.js`;
- `tests/browser_edit_server.py`;
- `tests/test_browser_edit_harness.py`;

As fontes Python de produto fora de `_catalog.py`, `_anchor.py` e dos recursos
gerados não mudaram. AGENTS, estado, arquitetura, segurança, plano e matriz
registram somente a entrega autorizada. Os requisitos normativos das seções
1–7 da especificação e as evidências históricas 1–6 permanecem idênticos.


## Encerramento e revisão

Todos os gates finais passaram sobre os mesmos recursos congelados. São 19
novos testes Node, 42 cenários de navegador (14 por engine) e quatro testes
Python acrescentados. Os 156 casos finais de browser passaram sem retries,
falhas ou skips. A primeira falha de startup Python permanece registrada acima;
a repetição integral passou, sem alegação de causa-raiz ou correção desse evento.

A inspeção de containers e processos não encontrou remanescentes da Etapa 7.
Os launchers confirmaram sua remoção no finally; o diretório do runner contém
somente .last-run.json (45 bytes), sem traces, screenshots, vídeos, HAR ou
conteúdo de sessão. Pins e lockfile permanecem intactos. Os 14 hashes finais
continuam iguais aos dos dois builds. Nenhum commit anterior foi alterado.

A revisão de escopo, segurança, lifecycle e efeitos não introduziu exceção ao
contrato aprovado. Normas de HTTP/origem/CSP, validação pré-bind, secrets,
planos e comportamento UI off permanecem protegidos pelos gates acumulados.
Reorder e edição de database/SQL não foram iniciados. Parar nesta Etapa 7,
com um único commit local, sem push; publicação e Etapa 8 dependem de revisão.
