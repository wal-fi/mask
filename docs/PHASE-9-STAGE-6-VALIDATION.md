# Fase 9 — validação da Etapa 6 (CRUD visual de datasources e policies)

Autorizada pelo usuário em 2026-09-28, localmente e sem push, depois da
publicação da Etapa 5 em `4d5b78f`. Decisões D-103–D-106, propostas desta etapa.
**O usuário aprovou explicitamente D-103–D-106, as capturas da Etapa 6 e o
fechamento da etapa em 2026-09-30** (selects truncados a 320 px e banner
duplicado aceitos como observações não bloqueantes). Não inicia a Etapa 7,
PGWire, bind externo, variável de ativação, MCP multi-datasource nem a definição
do datasource default (adiada para a Etapa 11, D-096). **O limite pós-conexão da
D-090 continua aberto**: a v2 segue ativável só pelo parâmetro interno do
composition root, e esta etapa não autoriza ativá-la para operação real.

## 1. Escopo entregue

Fluxos visuais sobre as nove escritas da D-093 (nenhuma rota nova):

| fluxo | rota | onde |
|---|---|---|
| cadastro com teste do rascunho, revisão e confirmação | `POST /datasources:test`, `POST /datasources` | Novo datasource (assistente de 7 passos da §9.1) |
| edição de nome, conexão, TLS, limites e destinos aceitos | `PUT /datasources/{id}` | detalhe, "Editar conexão e limites" |
| troca de senha write-only | `POST /datasources/{id}:rotate-credential` | detalhe, "Trocar senha" |
| teste sem publicação | `POST /datasources/{id}:test` | detalhe, "Testar conexão" (só habilitado, §6.1) |
| habilitar / desabilitar | `POST /datasources/{id}:enable` / `:disable` | detalhe |
| remoção confirmada pelo alias | `DELETE /datasources/{id}` | detalhe, "Remover" |
| edição da política por datasource | `PUT /datasources/{id}/policy` | abas Masking e SQL, "Editar política" |

A política é editada em linguagem humana, com ordem visível e reordenação por
teclado; os parâmetros de cada transformer aparecem só quando ele está
selecionado, e só os visíveis são enviados. As funções PostgreSQL liberadas não
são editáveis e nunca são enviadas (D-050).

## 2. Contratos preservados

- **v1 intacta.** As sete seções seladas da Etapa 8 (`views`, `editors`,
  `bindings`, `messages`, `format`, os 110 primeiros modelos e as 19 primeiras
  chamadas) são idênticas ao commit `4d5b78f`, e o teste `APPROVED` passa sem
  alteração. As leituras v2 da Etapa 5 (`models[110:147]`, `calls[19:23]`)
  mantêm seus selos. Os fluxos de escrita da v1 não mudaram; a regra de uma
  escrita por vez passou a valer para v1 e v2 juntas.
- **Inventário exato.** Somente as nove escritas da D-093, conferidas no Python
  (`V2_WRITES`, espelho de `V2_WRITE_ROUTES` por teste), no verificador público
  e no transporte (uma escrita v2 só sai por `submit`).
- **Fronteira pública/privada (D-062/D-099).** O JS não conhece nomes de campo,
  categorias ou rótulos. A inspeção pública pegou, durante o desenvolvimento,
  `revision`, `policy`, `datasource_id`, `removed`, `changed`, `closing` e
  `valid` (de `aria-invalid`); todos foram retirados do código público ou
  passaram a vir da apresentação, sem ampliar exceções.
- **Segredos.** A senha só existe num campo `type=password`
  (`autocomplete=new-password`), nunca é preenchida nem relida, aparece no
  resumo como "Informada (não exibida)" e é apagada ao concluir, descartar,
  sair, fechar, no `pagehide` e no logout. DSN e chave nunca são campos.
- **CSP, mesma origem, token em memória, sem recurso externo, sem dependência
  nova, sem editor SQL, consulta ou resultado.**

## 3. Estados de uma escrita (D-105)

| estado | categorias | efeito na UI |
|---|---|---|
| concluído | `2xx` | fecha, relê e anuncia o resultado na linha de status |
| recusado | recusas de validação, destino, conexão, capability, alias, confirmação, fronteira | nada mudou; volta ao rascunho, erros ligados aos campos |
| capacidade esgotada | `DATASOURCE_BUSY` | nada mudou; tentar depois, por gesto |
| conflito | `REVISION_CONFLICT` | rascunho preservado, não aplicado sobre a versão nova; "Descartar e reler" |
| bloqueado | `CATALOG_WRITE_ERROR`, `CATALOG_BLOCKED`, `DATASOURCE_SERVICE_UNAVAILABLE` | escritas desligadas até reiniciar |
| incerto | `CATALOG_OUTCOME_UNCERTAIN`, `INTERNAL_ERROR`, categoria desconhecida, resposta perdida, timeout | escritas desligadas até uma leitura nova bem-sucedida |

Um teste nunca desliga escritas. Não há retry, rebase, fila nem rollback
automático.

## 4. Provas

`frontend/browser/datasources.spec.js`, contra o composition root real, o
catálogo cifrado real e as rotas v2, com o harness em modo de escrita
(`MASKGW_BROWSER_WRITE=1`, adapters duble para o upstream), nos três engines:

1. assistente: campo obrigatório bloqueia o passo; teste do rascunho é **um**
   `POST :test` sem carimbo e sem efeito (catálogo sem o alias); cadastro é **um**
   `POST`, o estado real fica habilitado e o candidato usou exatamente a senha
   digitada;
2. edição, troca de senha (senha nova usada pelo candidato), teste,
   desabilitar/habilitar e remoção: alias errado é `CONFIRMATION_MISMATCH` sem
   remover; alias certo remove; sequência exata de escritas, sem retry;
3. política: reordenação por teclado com foco preservado, regra nova com só os
   parâmetros visíveis, funções liberadas nunca enviadas, ordem relida;
4. duas sessões: rascunho velho recebe um `409`, fica preservado e não é
   reenviado; a versão da outra sessão prevalece;
5. candidato recusado por conexão e por capability volta ao rascunho; resposta
   perdida depois de aplicada e timeout antes do servidor são resultado
   desconhecido e desligam escritas até reler; o estado real é conferido;
6. falha depois do replace (incerta) e antes dele (bloqueio): leituras
   recusadas, nenhuma ação ou assistente sobre leitura recusada;
7. 320, 640 (200%) e 1280 px, temas claro e escuro, contraste AA ≥ 4,5 dentro
   dos diálogos, sem rolagem horizontal, foco preso, Esc com confirmação e
   logout sem resto de senha;
8. `pagehide` descarta o rascunho aberto e a senha.

Em todos: nenhum token, senha digitada ou segredo upstream em URL, storage,
atributo, texto, valor de campo, console, log ou auditoria; a sonda aceita só
auditoria `datasource_*`.

Unidades: `surface.test.js` (transporte: um pedido por escrita, corpo conferido
antes do voo, token no corpo recusado, identidade com sufixo de ação, envelope
fechado, perda de resposta, uma escrita por vez, `read`/`check` sem alcançar
escrita) e contraexemplos do verificador público; `test_admin_ui_actions.py`
(os mesmos contraexemplos no Python, cobertura das categorias, motivos
fechados, nota da D-068).

## 5. Achados durante a etapa

- O gerador tratava todo padrão de string como ID opaco e transformava o alias
  num ID de exceção; corrigido para só padrões de ID (saída da v1 inalterada).
- Diálogo sem botão "Fechar" depois de resultado desconhecido (o descarte do
  rascunho apagava também o desenho); corrigido com `scrub()`.
- Foco perdido ao mover uma regra para o topo (o botão de subir fica
  desabilitado); o foco passa ao outro sentido do mesmo item.
- A classe `flag` do campo colidia com a pílula de estado; renomeada.
- O botão final do assistente repetia "Novo datasource"; passou a
  "Cadastrar datasource".

## 5.1 Correção da revisão (2026-09-29)

A revisão apontou dois defeitos de UX na saída por Esc, ambos sem escrita
insegura, e foram corrigidos localmente (sem emenda, sem push):

- **Esc num resultado desconhecido/incerto/bloqueado** fechava o diálogo sem
  reler; a tela ficava desatualizada, com botões de ação aparentemente
  habilitados que não faziam nada. Agora Esc segue o mesmo fluxo do botão
  "Fechar": relê o estado (e, ao reler, a dúvida é liberada).
- **Esc sobre um rascunho em conflito** descartava sem reler. Agora segue o
  mesmo fluxo de "Descartar e reler": a pergunta de descarte é preservada e,
  depois do descarte, relê.

A correção vive só em `frontend/src/desk.js`: `modal` passou a receber uma ação
de Esc por estágio e `start` a fornece — nos estágios `conflict` e `ending` ela
chama `leave(hooks.refresh)`, nos demais `leave(()=>{})` como antes. A limpeza
da senha, a confirmação de descarte, o bloqueio de escritas durante a dúvida e a
ausência de retry/rebase/rollback continuam intactos. Não muda apresentação,
CSS, categorias nem inventário: só `ui.js` e seus portadores de hash
(`_anchor.py`, `manifest.json`) foram regerados; `presentation.json` e o selo
mantêm o hash. Nenhuma captura mudou (nenhuma depende de Esc).

Regressão em `frontend/browser/datasources.spec.js`: dois testes por Esc
(desconhecido → fecha e relê, escritas retornam, uma só escrita sem retry;
conflito → confirma descarte, relê, um só PUT sem rebase), cada um provando foco
fora do diálogo fechado e nenhuma escrita extra antes da releitura. Ambos
**falham contra o código anterior** à correção e passam depois, nos três engines.

## 6. Capturas

Fixture sintética (D-098), sem backend; a senha é um valor descartável num
campo mascarado. Novas: `09-cadastro-inicio`, `09b-cadastro-politica`,
`09c-cadastro-teste`, `10-cadastro-revisao` (substituem as do protótipo),
`17-editar-rascunho`, `18-editar-revisao`, `19-conflito`, `20-politica-editor`,
`21-remover` e `22-resultado-desconhecido`, em Chromium claro e escuro a 1280 e
320 px; `17-editar-rascunho` também em Firefox e WebKit. **Aprovadas
explicitamente pelo usuário em 2026-09-30**, com os selects truncados a 320 px e
o banner de cadastro duplicado aceitos como observações não bloqueantes.

## 7. Ambiente

Windows 11 Pro 10.0.26200; Python 3.11.3; Node 24.20.0 e npm 11.19.0 fixados;
Playwright 1.63.0 com Chromium 1243, Firefox 1543 e WebKit 2359; PostgreSQL
16.15 em contêiner descartável `postgres:16-alpine`, só em `127.0.0.1`, com
senha aleatória em arquivo privado temporário, removido ao final. Nenhum banco
existente foi usado.

## 8. Resultados medidos

| gate | resultado |
|---|---|
| build determinístico | dois builds, 8 arquivos com hashes idênticos (4 recursos, âncora, apresentação e schema privados) |
| inspeção pública | limpa (vocabulário v1 por substring, v2 por token, guarda de reconstrução) |
| typecheck (TypeScript strict, `checkJs`) | aprovado, fontes e bundle |
| testes Node | **306/306** (+21: 15 contraexemplos do verificador e 6 do transporte) |
| Python direcionado | inventário (selos da Etapa 8 e 5 inalterados, selo e inventário da Etapa 6, espelho do roteador), recursos, grupos/páginas e `test_admin_ui_actions.py` (20) aprovados |
| **suíte Python integral**, PostgreSQL 16.15 | **4.197 testes: 0 falhas, 0 erros, 8 skips** (os condicionais de POSIX já registrados; nenhum por DSN); 613 s |
| **matriz completa, três engines, checkout** | 246 testes (82 por engine): 245 aprovados e 1 falha no WebKit, em `console.spec.js › keyboard reaches every navigation entry`. O teste da Etapa 5 conferia o foco do título de "Novo datasource" sem esperar a leitura da lista, que o assistente real faz; falhava em 3 de 5 repetições. Passou a esperar o assistente pronto, como as outras entradas, com a mesma asserção: 10/10 no WebKit |
| arquivos alterados depois da matriz, três engines | `console.spec.js` e `datasources.spec.js` completos (incluindo o teste novo de `pagehide`): **51/51** (17 por engine) |
| **matriz completa na revisão** (2026-09-29, árvore do commit `1cc6000`, PostgreSQL 16 descartável, `retries: 0`, sem deselect nem skip) | **249/249** (83 por engine: os 82 anteriores mais o teste de `pagehide`), 0 falhas, 0 skips, 0 flaky; 2.853 s |
| wheel / sdist | 99 e 124 entradas; wheel 317.495 bytes, SHA-256 `8c57de33111080efd30270a71cb654f88d640e48f7f813c26db16f3829ca2b27`; sdist 274.260 bytes, SHA-256 `2773bee73a78ccfd1e5a9b7ed3169c9fc4eeb0f0b6719fe8bb7e6a1efa51143b`; sem `frontend/`, `tests/`, `docs/`, capturas, `.codex` ou links |
| sondagens instaladas | Fase 8 aprovada nos dois pacotes; console v2 aprovada nos dois (quatro leituras e exatamente as nove escritas, conferidas contra o roteador instalado) |
| contraprovas de isolamento | sem `-I`, Node no PATH e site errado: recusados nos dois pacotes |
| navegador contra o pacote instalado | wheel **54/54** e sdist **54/54**: console, pacote e os nove fluxos da Etapa 6 nos três engines |
| Ruff, format e mypy strict | aprovados; 176 arquivos |
| `git diff --check` | aprovado |

Todas as medições acima foram feitas sobre a **árvore do commit `1cc6000`**. A
sondagem do console instalado afirmava o contrato da Etapa 5 ("quatro leituras,
todas GET"); passou a afirmar, com o mesmo rigor, as quatro leituras e exatamente
as nove escritas aprovadas.

## 8.1 Resultados da correção da revisão

As medições abaixo foram tiradas da árvore com a correção dos dois caminhos por
Esc em `frontend/src/desk.js` e os dois testes de regressão em
`frontend/browser/datasources.spec.js`, **ainda não commitada quando os gates
foram medidos** (2026-09-29), sobre o HEAD `1cc6000`. Só `desk.js`,
`datasources.spec.js`, `ui.js`, `_anchor.py`, `manifest.json` e este documento
foram tocados; `presentation.json` e o selo não mudaram. Essa mesma correção
**agora integra o commit de fechamento da etapa** (2026-09-30), sem alteração de
comportamento nem dos números aqui registrados. Cada rodada de navegador foi
registrada separadamente.

| gate | resultado |
|---|---|
| typecheck + inspeção pública + build determinístico | aprovados; dois builds idênticos, `ui.js` SHA-256 `dbb51c17c677b4c339d69bdff2e8a4e6ba5b9175eedd377bb30857004fce265c`; `presentation.json` inalterado |
| testes Node | **306/306** |
| regressão dos dois testes por Esc contra o código anterior | ambos **falham** sem a correção (chromium), confirmando que capturam os defeitos |
| **matriz integral, três engines, checkout — rodada 1** (`retries: 0`, sem skip nem deselect, PostgreSQL 16 descartável) | **255/255** (85 por engine), 0 falhas, 0 skips, 0 flaky; 1.340 s |
| **suíte integral do wheel instalado, três engines — rodada A** | **253/255**: 85 chromium, 85 webkit, **83 firefox**; **2 timeouts (60 s) na Firefox**, em `batches.spec.js › obsolete permutation cannot be reviewed after another tab deletes an ID` e `editing.spec.js › already adopted is reconciled without another adoption` (ambos testes v1, sem relação com `desk.js`); gate **reprovado** nesta rodada |
| investigação dos 2 timeouts | os dois testes alcançaram `harness-page` (~3 s) mas nunca `harness-acted`, sem erro nem stderr; reexecutados isolados na Firefox instalada **3/3 aprovados** em ~7 s cada; nas rodadas 1 e B os mesmos testes passam. Os dois testes são da v1 e não exercitam `desk.js`, então não têm relação com a correção por Esc. **Causa dos timeouts: indeterminada** — não foi reproduzida nem isolada uma raiz; não se afirma contention da Firefox nem se descarta defeito de teste sem prova |
| **suíte integral do wheel instalado, três engines — rodada B (reexecução idêntica)** | **255/255** (85 por engine), 0 falhas, 0 skips, 0 flaky; 1.339 s |
| wheel regerado | 99 entradas, 317.714 bytes; SHA-256 do zip não é reprodutível byte a byte (o zip do wheel carrega metadados voláteis): rodada anterior `5d1b2d5a…6893`, esta `d434aebe0164865a286f07a97d5cecf676f18af92184e21dd3a343187a947e4d` |
| conteúdo gerado e instalado do `ui.js` | o `ui.js` gerado pelo build (`src/maskgw/admin/ui/assets/ui.js`, 221.011 bytes, SHA-256 `dbb51c17…265c`) é o mesmo arquivo que o wheel instala em `…/site-packages/maskgw/admin/ui/assets/ui.js`, conferido byte a byte |
| sondagem do console instalado (wheel) | aprovada: quatro leituras, exatamente as nove escritas, sem segredo |

A rodada A (253/255) fica registrada como **reprovada**, com os dois timeouts e
sua investigação anexados; não foi convertida em aprovação. A rodada B (255/255)
é a **repetição integral limpa**. A causa dos dois timeouts permanece
**indeterminada**: não há raiz reproduzida. O **usuário aprovou o fechamento da
Etapa 6 em 2026-09-30 apesar desse desvio documentado**, ciente de que a rodada A
consta como reprovada e de que a rodada B é a repetição limpa.

## 9. Limitações

- O limite pós-conexão da D-090 continua aberto: um upstream que autentica e
  para de responder prende o handler administrativo. A UI mostra resultado
  desconhecido depois dos 30 s do navegador, mas o servidor continua; por isso a
  v2 não pode ser ativada para operação real antes da Etapa 7.
- `last_test` continua "Nunca verificado" (D-091): o resultado de um teste não
  é persistido.
- Os selects nativos truncam texto longo a 320 px; o texto completo aparece ao
  abrir.
- O datasource default do MCP não existe nesta etapa (D-096).
