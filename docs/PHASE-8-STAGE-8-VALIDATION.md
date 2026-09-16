# Fase 8 — Evidência da Etapa 8

**Estado:** Etapa 8 concluída; gates acumulados verdes; commit local para revisão.
**Medições:** 2026-09-15 e 2026-09-16. **Escopo:** reorder de regras, database e SQL aditivo.

## Checkpoint e publicação da Etapa 7

Confirmados master, HEAD `57cc7522642d3fe3dddd10187b996ba71fc38e3f`,
origin/master `db33fa770e1b675ee23ad554a84c93a7e9e2f358`, árvore limpa e
1 ahead / 0 behind. Autor e committer `w.filho <w.filho@live.com>`;
trailer `Co-Authored-By: Codex <noreply@openai.com>`.

Foi publicado exatamente `57cc7522642d3fe3dddd10187b996ba71fc38e3f`, sem amend,
rebase ou alteração de arquivos. O fetch confirmou HEAD igual a origin/master,
0/0 e árvore limpa, com identidade/trailer preservados. A primeira solicitação
de execução do push expirou na revisão automática antes de criar o processo;
a única repetição autorizada concluiu a publicação e foi verificada por fetch.
Esta rodada não publica a Etapa 8 nem inicia a Etapa 9.

## Contratos implementados

| Ação | Corpo dedicado, além de expected_revision da base |
|---|---|
| POST /admin/v1/rules:reorder | rule_ids: permutação completa e exata da base |
| PUT /admin/v1/database | statement_timeout_ms e max_rows, ambos sempre presentes |
| PUT /admin/v1/sql | denied_functions: somente inclusões literais |

`author.js` deriva os três perfis de modelos, operações e projeções privadas.
`workbench.js` integra esses perfis ao coordenador e transporte existentes.
Não surgiram chamadas, rotas, modelos ou permissões novos. A gramática,
catálogo Python, onze contratos wire, dez escritas permitidas, dependências,
lockfile v3 e pins permanecem intactos. A apresentação ganhou quatro controles
(total 48), conservando 110 modelos, 19 chamadas, seis vistas e oito editores.

Reorder trabalha sobre IDs estáveis e a lista-base completa. Busca é local à
exibição; mover para cima/baixo, por teclado, usa vizinhos da ordem completa.
As posições visíveis começam em 1, inclusive na vista readonly por cópia
orientada pelo binding order; DTOs, snapshot e semântica de transporte não
mudam. Revisão exibe o candidato completo e exige confirmação final. Cancelar
e descartar restauram a leitura-base sem request ou mudança no servidor.
Uma permutação de outra lista, inclusive após exclusão por outra aba, não é
rebaseada: revisão incompatível conserva o rascunho até decisão humana.

Database exige inteiros seguros/literais, nos intervalos 100–600000 e
1–1000000. Booleanos, frações, strings coercíveis, inteiros inseguros e extras
não chegam ao request. A entrada textual do formulário aceita só dígitos sem
sinal, expoente, ponto, espaços ou zeros iniciais. O payload contém os dois
limites mesmo se somente um tiver mudado.

SQL oferece lista-base readonly e novos nomes separados por linha. O corpo
contém somente inclusões, sem remover/renomear itens anteriores. Não faz
casefold ou deduplicação autoritativa; preserva diferenças de caixa e Unicode
no envio. A releitura Python confirma a lista declarada deduplicada e a política
efetiva normalizada. `allowed_pg_functions` não é enviado nas mutações em
qualquer forma, inclusive null. A validação explícita usa o candidato completo
base+rascunho, conservando esse campo protegido, exceptions e demais campos;
somente a projeção transitória de validate omite IDs/revision, como nas etapas
anteriores. Toda mudança de rascunho ou revisão de base invalida a prova anterior.

Todos os fluxos conservam snapshot-base, revision-base e rascunho, uma escrita
pendente, gesto explícito, ausência de autosave/fila/retry/rebase/rollback
automático. Conflito e busy preservam dados. Releitura não resolve por si só
resultado desconhecido ou durabilidade incerta: novas escritas permanecem
bloqueadas nessa sessão, mesmo após descartar o diálogo. Sucesso com readback
falho permanece “salva; visualização ainda não atualizada” e requer releitura
manual. Logout, 401, pagehide/pageshow e BFCache usam a limpeza existente.

## Gates medidos

| Gate | Resultado |
|---|---|
| npm ci --ignore-scripts | exit 0; 13,59 s; instalação congelada, pins/lock inalterados |
| Build 1 / build 2 | exit 0; 29,17 s / 23,11 s; 14 saídas idênticas e LF |
| checkJs strict/noEmit | exit 0; 8,67 s; fontes, testes e ESM final sem supressões/any |
| Inspeção pública | exit 0; 1,42 s; 193 termos, literal/decodificada/AST, sem exceções novas |
| Node | 241 aprovados; 0 falhas/skips/xfail; 102,59 s de gate |
| Navegadores acumulados | 189 aprovados, 63 por engine; zero falhas/skips/retries; 2232,83 s; Chromium 153.0.8010.12 (1243), Firefox 155.0 (1543), WebKit 26.6 (2359) |
| Python integral + PostgreSQL 16 real | 3808 coletados, 3800 aprovados, 8 skips POSIX; zero falhas/erros; 673,94 s (JUnit 652,983 s); PostgreSQL 16.15 |
| Ruff / format / mypy strict | exit 0: Ruff 0,89 s; format 1,22 s (137 arquivos); mypy strict 3,67 s (137 arquivos) |
| git diff --check | exit 0, após revisão final |

Wheel `maskgw-0.1.0-py3-none-any.whl`: 81 entradas, 203524 bytes,
SHA-256 `7e0107278cc4f4f190ca706ae3264be07e17ea14a5dba0f309a45aaa3f34a15a`.
Sdist `maskgw-0.1.0.tar.gz`: 104 entradas, 172443 bytes,
SHA-256 `72b5ed652ec5f59f40e7f44a27fce42842280608fbac5fe0e8ed11941cbb8c4d`.
Gate de pacote: exit 0 em 55,78 s; setuptools 68.2.2, wheel 0.45.1 e
packaging 24.2. Construção e instalação isoladas fora do checkout; smoke
Python -I -S com PATH restrito confirmou ausência de Node/npm, quatro recursos
válidos e bytes iguais aos do checkout. Sem frontend, testes, fixtures,
sourcemaps ou tipos privados nos pacotes. Os hashes de arquivos compactados
identificam esta execução, não prometem builds de wheel/sdist bit-reprodutíveis.

Somente estas seis saídas geradas diferem da Etapa 7:

- `frontend/private/presentation.json`
- `src/maskgw/admin/ui/assets/manifest.json`
- `src/maskgw/admin/ui/assets/presentation.json`
- `src/maskgw/admin/ui/assets/ui.css`
- `src/maskgw/admin/ui/assets/ui.js`
- `src/maskgw/admin/ui/_anchor.py`

HTML, esquemas/contratos/tipos privados, nomes dos modelos, vocabulário e
catálogo Python continuam byte a byte iguais. Manifesto e âncora foram
regenerados pelos comandos de build, não corrigidos manualmente.

### Recursos finais medidos

| Recurso | Bytes | SHA-256 |
|---|---:|---|
| index.html | 351 | `f18c78d7a27b30db371a8d865510d00e744b644ae635203e51c5ccd0811fa699` |
| ui.js | 112807 | `476c3c056f5168a3f5dcffc43652a131279f1a447364f1c5b76fd650dee1dda2` |
| ui.css | 1682 | `4a360166bc0cf099eb5b7749dfa4013117d75867383142b69c94744c989ab5b2` |
| presentation.json | 39704 | `0ee31f73edd994ac98694ecfac36197e7bac3690879e28c7e459ce11accc9a43` |

## Provas adversariais e efeitos reais

Os 44 testes novos em `frontend/test/batches.test.js` verificam tipos,
permutação, origem/imutabilidade da base, corpos fechados, preservação dos
campos protegidos, SQL literal e offsets somente de apresentação. Testes
acumulados continuam cobrindo gramática, ciclos/protótipos, limites, hashes,
manifesto, tipagem negativa, dez comandos e a máquina de estados completa.

`frontend/browser/batches.spec.js` exercita os três engines contra o composition
root real. O harness privado verifica cada request, arquivo, revision, digest,
snapshot, IDs/exceptions/conteúdo, auditoria e resultados após falhas. Reorder
inverte a regra vencedora observada via MCP; max_rows reduz o retorno de três
linhas para uma; upper é permitida antes da inclusão e negada depois. Reinicialização conserva esses efeitos.
Não há execução SQL na UI: somente o cliente MCP do harness consulta o servidor
para comprovar a consequência das mutações HTTP. Nenhuma rota de fault injection.

## Execuções incrementais e diagnóstico

Foram preservados os logs sanitizados das tentativas anteriores ao gate final:

- Primeira rodada incremental: 24/27 aprovados, três falhas no cenário SQL.
  As expectativas ainda em construção confundiam grafia declarada/efetiva e
  a fixture Unicode estava sendo ampliada. Não houve alteração da normalização
  do produto para satisfazer o teste.
- Segunda rodada: 30/33 aprovados. O Chromium falhou ao consultar o diálogo SQL
  imediatamente após abri-lo; o teste agora aguarda o campo ficar visível,
  depois da leitura assíncrona. No Firefox, houve uma falha esperando conflito
  e um timeout no cenário de permutação obsoleta.
- Diagnóstico isolado no Firefox: conflito normal aprovado, cenário obsoleto
  novamente em timeout. Com marcadores de passos/estados sanitizados, a repetição
  isolada do cenário obsoleto passou em 26,36 s. Esses resultados não estabelecem
  causa-raiz dos eventos no Firefox. A ocorrência permanece registrada mesmo
  se a suíte final passar; nenhum retry de teste, skip ou xfail foi introduzido.
- O primeiro build da implementação apontou o identificador `positions`, que
  contém o termo privado `position`; ele foi renomeado para `offsets`, sem
  ampliar allowlist. A tipagem inicial detectou narrowing/tupla nos testes,
  corrigidos sem supressões. A execução Node no sandbox teve spawn EPERM;
  a execução autorizada com subprocessos passou.
- Após pytest aprovado, Ruff recusou complexidade/quantidade de statements e
  uma linha longa no harness. As verificações foram extraídas para helpers,
  sem excluir asserções ou alterar o produto. Ruff, format e mypy completos
  passaram depois disso; o harness final é exercitado pela suíte de browsers.

Os diagnósticos imprimem somente nomes de testes, estados/etapas de enum fechado,
números de linha e durações. Nenhum texto de resposta, DOM, token, DSN, SQL executado ou
valor administrativo vai para o reporter. As novas esperas são do harness;
a aplicação mantém os mesmos timeouts e nenhuma repetição automática.

### Rodada acumulada e protocolo do harness

A primeira execução acumulada terminou com 180/189 aprovados: sete timeouts
no Firefox e duas falhas de asserção no WebKit. No cenário de ID obsoleto,
os marcadores chegaram até o fechamento da outra aba; não se atribui causa
única a todos esses eventos. A leitura do harness usava `stdout.once("data")`
como se um bloco de stream fosse uma resposta completa. Essa suposição foi
substituída por enquadramento de linhas, com dois testes Node que dividem e
agrupam respostas, e rejeitam EOF vazio/parcial, fechamento e linha excessiva.
As mesmas asserções de porta/"ok", stderr e exit code foram preservadas.
Marcadores fechados identificam encerramento de browser e subprocesso.
O módulo é exclusivo de testes, não embarcado nem servido.

Após a retomada, o Docker estava indisponível. O diagnóstico local apontou
sockets IPC residuais inacessíveis. Foram preservados por renomeação diretórios
verificados contendo somente sockets vazios, e o engine 29.7.2 voltou a iniciar.
Backups locais mantidos: `%LOCALAPPDATA%/Docker/run-stage8-socket-backup-20260915`,
`%LOCALAPPDATA%/Docker/run-stage8-recovery-2` e
`%LOCALAPPDATA%/docker-secrets-engine-stage8-socket-backup-20260915`.
Não houve reset de fábrica, alteração de credenciais, imagens ou volumes.
O PostgreSQL dos gates continua sendo 16.15 em container descartável loopback.

Os sete cenários que tiveram timeout no Firefox passaram na repetição com o
harness final (195,84 s). Cada caso terminou com browser e subprocesso fechados,
stderr verificado e exit code zero; container removido. A suíte Node inteira
final passou com 241 testes, incluindo os dois testes de framing. Os quatro
testes Python de apoio de EditProbe também passaram após extração dos helpers.
Essas correções não autorizam atribuir todos os eventos anteriores à mesma
causa; os resultados históricos permanecem registrados.

A segunda execução acumulada terminou com 186/189 aprovados: timeout no
Firefox em permutação obsoleta e navegação de histórico, e no WebKit em limites
inteiros inválidos. Dois casos chegaram ao marcador de fechamento do browser;
o caso obsoleto não forneceu localização suficiente. Isso não prova uma causa
comum nem uma regressão do produto. Foram acrescentados tempos monotônicos de
launch, porta, página, ação e fechamento, além da duração reportada pelo runner.
Somente números e etapas fechadas são serializados; os limites de tempo,
asserções, política sem retry e código do produto permaneceram iguais.

O diagnóstico desses três cenários nos três engines passou: 9/9 em 135,70 s,
com confirmação de fechamento de browser e subprocesso em todos os casos.
A execução isolada não substitui o gate acumulado. Nenhuma causa não comprovada
é atribuída às ocorrências anteriores.

A rodada seguinte foi interrompida deliberadamente durante a revisão, com
59 cenários aprovados e sem resultado integral (443,33 s). O processo do runner
e seus filhos foram encerrados e o wrapper confirmou a remoção do container.
Ela não conta como gate aprovado. A revisão encontrou uma lacuna no teste SQL:
consultava lower, já negada pela fixture inicial, em vez de comprovar o efeito
de uma inclusão nova. O harness agora consulta upper antes de qualquer mutação
(permitida, primeira regra vencedora e três linhas), e depois da inclusão e do
restart (recusada). O código do produto e os quatro recursos não mudaram.
Ruff, format e mypy passaram após esse reforço; a tipagem também, antes da
nova execução acumulada completa sobre um único snapshot.

A execução acumulada final passou integralmente: 189/189, 63 por engine,
sem falhas, skips ou retries, em 2232,83 s. Todos os casos chegaram ao marcador
de subprocesso encerrado; a versão de cada navegador foi confrontada com o pin.
A suíte Python também foi repetida sobre os arquivos finais: 3800/3808,
somente oito skips POSIX, em 673,94 s (JUnit 652,983 s), PostgreSQL 16.15.
Ruff/format/mypy strict finais passaram. As duas execuções usaram containers
separados, descartáveis e limitados a loopback; ambos foram removidos.

## Revisão de segurança, lifecycle e limites

Revisado o diff: nenhum arquivo de produto Python fora dos recursos e de
`_anchor.py` mudou. `commands.js`, `coordinator.js` e `transport.js` permanecem
byte a byte iguais. O catálogo é a única origem de chamadas; a UI não recebe
URL/método/campo livre. A permutação é confrontada com o snapshot original,
campos extras são recusados antes da projeção, e candidato de validação é cópia
congelada da base com somente a operação proposta.

A renderização usa texto e controles DOM. Nenhum innerHTML, store, cookie,
recurso externo, mudança de origem/Host/headers ou expansão de autenticação
foi introduzido. Os perfis compartilham o bloqueio de sessão e limpeza existente.
A revisão de base é explícita; um novo conjunto de IDs não é preenchido nem
corrigido silenciosamente. A autoridade de nomes SQL continua Python.

Skips legítimos da suíte integral Windows, todos preexistentes:

- `test_admin_adversarial.py:431`, `test_admin_http_audit.py:591`,
  `test_admin_http_writes.py:966`, `test_admin_service.py:910` e
  `test_config_filesystem.py:465`: fsync de diretório POSIX;
- `test_config_filesystem.py:121`, `:129`, `:140`: bits de modo POSIX.

Nenhum skip por ausência de MASKGW_TEST_DSN, deselect ou filtro de pytest.
O processo de testes usou somente o ajuste temporário de pilha Windows de
64 MiB documentado em D-041, sem modificar produto/testes para contornar o caso.
O warning preexistente de pytest sobre match="" permanece sem silenciamento.

Permanecem os limites de plataforma já registrados: evento BFCache persistido
e histórico/reload nos três engines, retorno BFCache nativo adicional no
Chromium; os testes não alegam BFCache nativo em Firefox/WebKit. Durabilidade
pós-commit é injetada no harness Windows preservando o replace real, sem
alegar fsync POSIX nativo. Não há auditoria externa de acessibilidade; provas
são automatizadas com teclado, foco, viewport e zoom acumulados.

Rollback continua pela flag existente: desabilitar UI preserva a Fase 7,
sem desfazer configurações persistidas. Recuperação operacional após resultado
desconhecido/durabilidade incerta continua humana, fora da UI. Nenhuma expansão
para SQL editor, resultados do banco, auditoria consultável, MCP, TLS, proxy,
bind externo ou qualquer item da Etapa 9.

## Arquivos e encerramento

Os 28 arquivos desta entrega:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/ARCHITECTURE.md`
- `docs/HANDOFF.md`
- `docs/PHASE-8-SPEC.md`
- `docs/PHASE-8-STAGE-8-VALIDATION.md`
- `docs/PHASE-8-TRACEABILITY.md`
- `docs/ROADMAP.md`
- `docs/SECURITY.md`
- `docs/TEST-PLAN.md`
- `frontend/browser/batches.spec.js`
- `frontend/browser/harness.js`
- `frontend/browser/replies.js`
- `frontend/browser/reporter.js`
- `frontend/private/presentation.json`
- `frontend/src/author.js`
- `frontend/src/screen.js`
- `frontend/src/workbench.js`
- `frontend/test/batches.test.js`
- `frontend/test/replies.test.js`
- `frontend/tools/build.js`
- `frontend/tools/presentation.py`
- `src/maskgw/admin/ui/_anchor.py`
- `src/maskgw/admin/ui/assets/manifest.json`
- `src/maskgw/admin/ui/assets/presentation.json`
- `src/maskgw/admin/ui/assets/ui.css`
- `src/maskgw/admin/ui/assets/ui.js`
- `tests/browser_edit_server.py`

Os 14 hashes finais permanecem iguais aos dois builds. O runner contém somente
`.last-run.json` (45 bytes), sem traces, screenshots, vídeos, HAR ou conteúdo
de sessão. A inspeção final não encontrou processos do harness ou containers
descartáveis desta etapa remanescentes. Pins e lockfile permanecem intactos.

A especificação normativa, D-061–D-064 e os limites de HTTP/segurança foram
preservados. A revisão documental corrigiu as referências de estado, os links
para evidência e as descrições residuais de ausência de controles de reorder,
database e SQL. Os registros históricos das etapas anteriores permanecem.

Encerrar com um único commit local sobre
`57cc7522642d3fe3dddd10187b996ba71fc38e3f`, autor e committer
`w.filho <w.filho@live.com>` e trailer
`Co-Authored-By: Codex <noreply@openai.com>`. A conferência posterior ao commit
deve confirmar master limpa, 1 ahead / 0 behind de origin/master. O hash completo
e essa conferência serão reportados na entrega, sem inserir no próprio commit
uma referência circular ao seu hash. Não publicar a Etapa 8 nem iniciar a Etapa 9.
