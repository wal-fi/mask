# Fase 8 — Evidência da Etapa 3

**Estado:** Etapa 3 concluída; gates acumulados aprovados. **Data:** 2026-09-10.
**Escopo:** flag bruta e validação de recursos antes de qualquer efeito operacional.

## Checkpoint, publicação e limite de autorização

O checkpoint confirmou `master`, HEAD
`d080886352920a663e8b0aa318761a083f54f7f7`, origin/master
`aebe31d0dbaba3238e97ae3ad13bf20fdd615211`, árvore limpa e 1 ahead / 0 behind.
Foi publicado exatamente d080886, sem emenda. O fetch seguinte confirmou
HEAD igual a origin/master, 0 ahead / 0 behind e árvore limpa. Autor e committer
`w.filho <w.filho@live.com>` e trailer
`Co-Authored-By: Codex <noreply@openai.com>` permaneceram intactos.

O trabalho desta rodada é filho desse commit e deve permanecer local. As
Etapas 4–9 e o push da Etapa 3 não foram autorizados. As decisões D-061–D-064
permanecem vigentes; nenhuma decisão funcional ou de segurança foi reaberta.

## Desenho implementado

`bootstrap/settings.py` define `RawSettings.get_raw(name) -> str | None`,
`EnvRawSettings` e `MappingRawSettings`. A fonte de ambiente devolve o valor de
`os.environ` sem transformação; a fonte injetada copia o mapping recebido.
Ausência e string vazia permanecem distintas. Nenhum repr expõe nomes/valores.
`resolve_admin_ui_enabled`, em `bootstrap/application.py`, compara exclusivamente com a string `1` e exige a
Admin API já habilitada. Não usa SecretProvider para ler a flag UI.

A leitura anterior da Admin API e dos secrets continua em seu provider
normalizado: token, DSN, HMAC e variáveis antigas mantêm seus contratos,
inclusive strip existente. O teste confronta fontes real/injetada, resolução
do token/DSN e saída efetiva do transformer HMAC. A fonte bruta também pode
ser injetada em `main(raw_settings=...)`; não há fallback ao ambiente quando
uma fonte explícita está presente.

`build_application(admin_ui_enabled=True)` exige `admin_http` e revalida token,
bind e porta antes de `load_resources()`, protegendo também chamadas diretas
com dataclass não validada. `admin_enabled=True` sozinho não satisfaz a
dependência. Nenhuma flag habilita implicitamente Admin HTTP.

O carregador da Etapa 2 permanece inalterado. Seus bytes imutáveis são mantidos
antes do filesystem e adotados por `Application`, que copia o mapping para
`MappingProxyType`. A propriedade `admin_ui_resources` retorna esse snapshot;
não relê disco. A aplicação conserva somente recursos estáticos em memória,
sem handles adicionais, mesmo depois de close até o fim da vida do objeto.
Nenhum recurso é passado a `_build_admin_http`, a handlers ou ao MCP.

## Ordem comprovada e falhas

O teste positivo executa o entrypoint com configuração/lock reais e servidor
HTTP real, usando doubles apenas para PostgreSQL e MCP nesse teste de ordem.
A suíte acumulada também executa a integração PostgreSQL real. Linha do tempo:

1. Flag bruta e dependência UI → Admin.
2. Settings administrativos válidos.
3. Manifesto, quatro recursos, catálogo e integridade validados em memória.
4. Acesso à configuração e aquisição do lock.
5. Compilação a partir do snapshot.
6. Conexão do adapter e composição do runtime.
7. Início HTTP e confirmação real do bind.
8. Construção e execução MCP em stdio.
9. Fim do MCP; parada/join HTTP; fechamento do runtime; liberação do lock.

Antes dos passos operacionais, as contraprovas bloqueiam carregamento/abertura
de configuração, aquisição de ConfigFileStore, conexão PostgreSQL, início de
thread, criação de socket e construção MCP. UI sem Admin não chega sequer a
settings ou assets. Settings inválidos não chegam a assets. Cada um dos cinco
arquivos internos (quatro recursos e manifesto) é removido e corrompido em cópia
temporária: nenhuma falha chega aos efeitos operacionais.

Incompatibilidades com hashes reancorados (incluindo o digest companheiro do
JS) também falham: versão de protocolo, catálogo não autorizado, referência de
modelo trocada, UTF-8 inválido, JSON com chaves duplicadas, campo extra no
manifesto e digest JS incorreto. Um controle positivo confirma que a cópia
válida reancorada é aceita. Isso prova validação semântica além do hash, sem
adulterar os assets de produção.
O entrypoint retorna 1 e escreve exatamente `maskgw: falha na inicializacao\n`
no stream stderr, sem valor, caminho, hash ou traceback. Os entrypoints reais
`python -m maskgw` e `python -m maskgw.mcp` também foram executados com UI=1 e
Admin=0: ambos retornaram 1, stdout vazio e essa mesma mensagem, comparada em
modo texto no subprocesso.

Após carregar, alterações de todos os arquivos em disco não mudam o snapshot;
recarregar o pacote adulterado falha. Falhas após criação da thread HTTP e na
construção MCP fecham thread/socket/conexão e liberam o lock, comprovado por
inventário de threads, nova aquisição real do lock e conexão recusada à porta.
O shutdown normal preserva a ordem existente e a idempotência.

## Compatibilidade e separação

Foram capturadas **40 respostas** do commit d080886, executado em uma cópia
temporária obtida por `git archive`, com configuração sintética, sem PostgreSQL
ou secrets de instalação. A captura está em `tests/fixtures/phase7-ui-off.json`;
`tests/admin_ui_compat_support.py` reproduz os mesmos pedidos contra a composição
atual. A comparação é literal de status, corpo (hex dos bytes) e headers
normalizados pelo cliente HTTP existente. Apenas o header temporal Date é
excluído. Não se alega igualdade da serialização bruta de nomes/ordem de headers.

As 40 respostas passam tanto com UI desligada quanto ligada nesta etapa:
GET/HEAD das oito leituras, quatro caminhos UI com/sem bearer, token incorreto,
Host inválido, Origin/Referer de mesma origem recusados, OPTIONS, POST UI e
caminho desconhecido. Nenhum recurso UI passa a ser público ou servido.
O fixture também fixa SHA-256 das **12 fontes HTTP/SecretProvider** da
referência (normalizando somente finais de linha de checkout para LF).

O repr da aplicação desligada continua exatamente
`Application(revision=0, state='ready', admin=True, admin_http=True)` no cenário
controlado; ligada, acrescenta somente `, admin_ui=True`. Nenhum token,
manifesto, hash, tamanho, caminho ou conteúdo foi adicionado às representações.
Com UI desligada, o teste substitui load_resources por uma falha obrigatória
se chamado e ainda assim conclui startup/HTTP/shutdown normalmente.

O teste estrutural da Etapa 2 foi atualizado para a autorização atual:
o composition root pode chamar o loader; HTTP não o importa, e o loader não
importa HTTP/runtime/MCP/logging. As demais regras de separação permanecem. A revisão também comparou ASTs
dos helpers `_build_admin_http`, `_load_configuration`, `resolve_admin_settings`,
`resolve_dsn` e `make_adapter_factory` com o commit publicado: todos idênticos.
Não há mudanças em HTTP, Host, Origin, Referer, Fetch Metadata, CSP, headers,
proxy_headers, schemas administrativos, persistência, runtime, auditoria ou MCP.
Nenhuma sessão, Web Crypto, fetch, tela, formulário, polling, CRUD ou máquina
de estados. Nenhum browser foi instalado ou usado; seu gate começa na Etapa 4.

## Gates medidos

Ambiente Python existente, sem atualização: Python 3.11.3, pytest 9.1.1,
Ruff 0.16.5, mypy 2.3.1, Pydantic 2.13.5, psycopg 3.3.4, FastAPI 0.141.1,
Uvicorn 0.52.4 e MCP 2.1.1. Versões lidas do ambiente que executou os gates.

- Testes direcionados de startup e recursos: **164 aprovados** (90 novos casos
  de startup mais os 74 casos de recursos existentes); essa execução inicial
precedeu o controle positivo adicional e a revisão de separação.
- Após o controle positivo e a correção de separação: **183 testes direcionados
  aprovados**, zero falhas/skips (91 de startup, 74 de recursos e 18 de separação
  de planos), em 34,902 s registrados no JUnit XML.
- Node 24.20.0, npm 11.19.0, TypeScript 5.9.3, Playwright 1.63.0 e
  @types/node 24.0.0 preservados; nenhuma mudança de dependências ou lockfile.

| Gate | Resultado |
|---|---|
| npm ci --ignore-scripts | Exit 0; 22,80 s |
| typecheck strict/checkJs/noEmit | Exit 0; 17,75 s |
| Node | 70 aprovados, zero falhas/skips; 62,28 s do processo |
| Build 1 | Exit 0; 68,39 s |
| Build 2 | Exit 0; 45,22 s; 14 arquivos idênticos entre builds e à Etapa 2 |
| Inspeção pública | Exit 0; 4,94 s; 193 entradas privadas derivadas |
| Entrypoints reais maskgw e maskgw.mcp | Exit 1 para UI sem Admin; stdout vazio e stderr fixo |
| Python completo / PostgreSQL 16.15 real | 2.477 coletados; 2.469 aprovados; 8 skips POSIX; zero falhas/erros/DSN skips/deselects; 471,22 s do processo, 461,625 s no JUnit |
| Ruff check src tests | Exit 0; 0,42 s |
| Ruff format --check src tests | Exit 0; 130 arquivos; 0,53 s |
| mypy --strict src tests | Exit 0; 130 arquivos; 1,47 s |
| git diff --check | Sem erros no working tree e no índice antes do commit |

A suíte completa usou `MASKGW_TEST_DSN` definido no ambiente do processo,
com PostgreSQL 16.15 real em container descartável, porta aleatória vinculada
somente a 127.0.0.1, imagem local `postgres:16-alpine` e sem pull. O container
e seu volume foram removidos ao terminar (remoção confirmada). Não houve
`--deselect`, filtro de marcadores, xfail ou skip por falta de DSN.

No Windows, o launcher temporário executou
`pytest.main(['-q', '-ra', '--junitxml=...])` em uma thread com
`threading.stack_size(64 * 1024 * 1024)`, conforme o ajuste de pilha documentado.
O processo aguardou a thread e propagou o exit code. Produto e testes não
foram alterados para esse ajuste. Builds não rodaram simultaneamente à suíte.

Os oito skips são os condicionais de plataforma preexistentes: cinco exigem
fsync de diretório POSIX e três exigem bits de modo POSIX. Identificação no XML:

- `test_admin_adversarial.TestLeakageNasFalhasDeEscrita.test_durability_error_depois_do_replace_nao_vaza`;
- `test_admin_http_audit.TestDurabilidade.test_durability_error_publica_com_revision_after`;
- `test_admin_http_writes.TestDurabilidade.test_fsync_de_diretorio_falho_publica_com_applied_true`;
- `test_admin_service.TestDurability.test_real_directory_fsync_failure_is_post_commit_on_posix`;
- `test_config_filesystem.TestValidation.test_group_writable_config_is_rejected_on_posix`;
- `test_config_filesystem.TestValidation.test_world_writable_parent_is_rejected_on_posix`;
- `test_config_filesystem.TestValidation.test_reused_lock_must_be_mode_0600_on_posix`;
- `test_config_filesystem.TestDurability.test_directory_fsync_failure_is_post_commit`.

Houve um warning preexistente de pytest sobre `match=""` em
`test_admin_http_lifecycle.TestBootstrapComAdminHttp.test_admin_http_implica_a_secao_critica`.
Nenhum teste foi silenciado ou modificado para ocultá-lo.

Os gates frontend terminaram antes de executar a suíte Python. Não foi
necessário regenerar bytes diferentes: os quatro recursos, manifesto,
âncoras/catálogo e sete arquivos privados de build ficaram idênticos ao
commit aprovado. O único arquivo frontend editado é o README de estado.
Wheel/sdist e browsers não foram repetidos como gate desta etapa: distribuição
foi validada na Etapa 2, recursos/distribuição não mudaram e os marcos seguintes
continuam exigidos conforme a matriz. Nenhuma dependência foi instalada no
produto; npm ci repôs somente o conjunto de desenvolvimento já fixado.

| Recurso interno | Bytes | SHA-256 inalterado |
|---|---:|---|
| `index.html` | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| `manifest.json` | 632 | `bf39e3bd400a801a549e9279b30fdb1e2b842b4beeb9276d74e05a9962676235` |
| `presentation.json` | 35212 | `0ec27cb80cb0111532e82cb2ef765810037550c33d06980b2aabc679f519a6ea` |
| `ui.css` | 232 | `c82fb0a81578900634c9e561cd7d16aaacfb9a0aec8802172ccd62c46ad786c4` |
| `ui.js` | 29178 | `fe73926f83926b9c92226eb72bff49c69e5d649c65b3f8accbf0e99c04b4785a` |

A primeira execução direcionada detectou dois testes novos incorretos: o helper
HTTP já envia token por default, então o caso sem autenticação precisava de
`token=None`. O teste foi corrigido e os 164 casos passaram. Nenhum finding
foi convertido em skip/xfail; nenhuma recusa do produto foi flexibilizada.

A primeira suíte completa encontrou uma violação de separação de planos:
`bootstrap/settings.py` importava settings administrativos. O teste original
`test_bootstrap_really_composes_the_admin_plane` permaneceu intacto; a checagem
de dependência foi movida para `bootstrap/application.py`, único importador
administrativo permitido. A fonte bruta passou a depender somente de stdlib.
A suíte completa foi repetida após a correção; os gates frontend continuam
aplicáveis porque nenhum de seus arquivos ou fontes administrativas mudou.

## Encerramento

Documentos atualizados: AGENTS, CLAUDE, HANDOFF, ROADMAP, ARCHITECTURE, SECURITY,
TEST-PLAN, especificação (somente estado/autorização), matriz e README frontend.
Evidências históricas das Etapas 1 e 2 permanecem intactas. A matriz relaciona
F8-002–005, 027, 029, 050–051, 054 e 062–065 às provas desta etapa, preservando
os comportamentos que só serão implementados nas Etapas 4–9.

Gates concluídos e revisão de segurança, lifecycle e separação finalizada.
Esta entrega deve permanecer em um único commit local com autor/committer
`w.filho <w.filho@live.com>` e trailer
`Co-Authored-By: Codex <noreply@openai.com>`. O checkpoint de saída exige master
limpa e 1 ahead / 0 behind de origin/master no commit d080886; a confirmação
do hash e desse estado acompanha o relatório final. Não publicar a Etapa 3
nem iniciar a Etapa 4 sem nova revisão/autorização.
