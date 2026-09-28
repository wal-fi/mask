# Fase 9 — validação da Etapa 5 (protótipo e Admin UX v2 somente leitura)

**Data:** 2026-09-24
**Base:** `c37be3669f50929b83bcb8344ab5e5c605f13731`, `master` igual a
`origin/master` (0/0), sem alterações rastreadas no início; `.codex/`,
`systeminfo` e `bash.exe.stackdump` não rastreados e preservados.
**Escopo autorizado:** Admin UX v2 somente leitura. Sem POST/PUT/DELETE novo,
coleta/envio de senha, CRUD de datasources, PGWire, ativação por ambiente, bind
externo, editor SQL ou resultados do banco. Etapa 6 e push fora.

Este documento registra somente o que foi medido nesta sessão.

## 1. Decisões apresentadas antes do código

| ponto | escolha aprovada | decisão |
|---|---|---|
| gramática fechada da Fase 8 (6 views, 19 chamadas, só `/admin/v1/`) | formato 2 com seção `console`; quatro `GET` sob `/admin/v2/`; seções v1 byte a byte | D-097 |
| capturas × §4.4 da Fase 8 | somente fixture sintética, script dedicado, reporter sem screenshot | D-098 |
| vocabulário privado da v2 (110 termos; 12 colidiam por substring) | verificação por token; só `password`, `status` e `never` compartilhados | D-099 |
| shell e tema; toolchain | v1 intacta num grupo "Política v1"; tema em memória; Node/npm fixados baixados e verificados | D-100 |

## 2. Estrutura e fluxos

Barra lateral única (Painel, Datasources, Novo datasource; grupo Política v1
com as seis vistas da Fase 8), cabeçalho com tema e Sair, uma região de status
e a região "Leitura". Fluxos: Entrar → Painel (ou, sem catálogo, Visão geral da
v1); Datasources → busca local → detalhe com abas Visão geral, Conexão, Masking,
Limites e SQL (setas, Home e End); Novo datasource → sete passos só de
navegação, com aviso de que nada é salvo, testado ou solicitado; Sair/401/
pagehide/BFCache → entrada. Estados: carregando, vazio, sem correspondência,
catálogo desligado (404), item removido (404), catálogo bloqueado ou
indisponível (503) e falha genérica, com texto acionável.

Revisão das capturas encontrou e corrigiu dois defeitos antes dos gates finais:
o protótipo marcava passos anteriores com "✓" — o que sugeriria teste ou
gravação — e passou a usar numeração neutra; e a porta aparecia formatada
("5.432") e passou a texto.

## 3. Implementação

| área | conteúdo |
|---|---|
| `src/maskgw/admin/ui/protocol.py` | formato 2, `console`, prefixo v2 só `GET`/`read`, limites de modelos 192 |
| `frontend/src/protocol.js`, `reader.js`, `transport.js` | verificação pública do console; identidade de item validada; 404/503 por status HTTP |
| `frontend/src/screen.js` | shell novo, painel, lista, detalhe com abas, protótipo, tema |
| `frontend/src/author.js`, `workbench.js`, `coordinator.js` | renomeios mecânicos de identificadores que colidiam com o vocabulário v2; filtro de prefixo na leitura de editores |
| `frontend/tools/generate.py`, `console.py`, `presentation.py`, `inspect.js`, `build.js`, `screenshots.js` | contratos e vocabulário v2 em arquivos novos, autoria privada, inspeção por token, CSS com tokens/temas, capturas |
| testes | `surface.test.js`, `console.spec.js`, `browser_console_server.py`, `installed_console_probe.py`; ajustes em `protocol.test.js`, `transport.test.js`, `reading.spec.js`, `package.spec.js`, `lifecycle.spec.js`, `harness.js`, `test_phase8_final_inventory.py`, `test_admin_ui_resources.py`, `test_admin_ui_startup.py` |

Selo da v1: `views`, `editors`, `bindings` e `messages` têm os hashes aprovados
da Etapa 8; os primeiros 110 modelos e 19 chamadas também. Os artefatos
privados da v1 (`vocabulary.json`, `wire-schemas.json`, `contracts.d.ts`,
`calls.json`) não mudaram.

Ajustes em testes da Fase 8, todos declarados: no teste de leitura com teclado,
a contagem de entradas da navegação (6 → 9) e a ordem de Tab passam a incluir as
três entradas v2; o contraexemplo "format number" passou a usar 1 e 3; a
mensagem interna `Request failed.` virou `Request unsuccessful.` em três
asserções; o hash da apresentação em `package.spec.js`; e a fixture de ciclo de
vida responde `/admin/v2/` com 404 JSON, como o servidor real sem catálogo.

## 4. Achado de ambiente

O `.venv` do checkout contém uma instalação não editável e antiga de `maskgw`
(`dist-info` de 2026-09-22). Sem `PYTHONPATH`, o harness de navegador importava
essa cópia em vez do checkout; uma primeira rodada de navegador nesta sessão foi
descartada por isso. O harness passou a definir `PYTHONPATH=src` no modo
checkout. O venv não foi alterado. Não se afirma nada sobre execuções
históricas.

## 5. Gates

Ambiente: Windows 11 Pro 10.0.26200; Python 3.11.3 nativo no venv do projeto;
Node 24.20.0 e npm 11.19.0 oficiais em pasta local (SHA-256 conferido contra a
lista SHASUMS256 obtida por HTTPS, sem verificação GPG); TypeScript 5.9.3;
Playwright 1.63.0 com Chromium 153.0.8010.12 (1243), Firefox 155.0 (1543) e
WebKit 26.6 (2359); PostgreSQL 16.15 em contêiner descartável da imagem local
`postgres:16-alpine`, só em `127.0.0.1`, com senha aleatória em arquivo privado
temporário, nunca impressa. setuptools 84.0.0, wheel 0.48.0, build 1.6.1.

| gate | resultado |
|---|---|
| `npm ci --ignore-scripts` nas versões fixadas | aprovado (6 pacotes) |
| typecheck | aprovado |
| testes Node | **271/271** (241 da baseline + 30 novos) |
| build determinístico | dois builds, 16 artefatos com hashes idênticos |
| inspeção dos artefatos públicos | limpa (substring v1 + token v2) |
| navegador, checkout, três engines, PG 16 | commit original: **213/213** (71 por engine; 2.131 s). Emenda: **216** (72 por engine). Na matriz integral, 215 aprovados e 1 timeout de carga em fluxo v1 do Firefox; o projeto Firefox inteiro foi reexecutado com 72/72 (seção 8) |
| wheel/sdist isolados | construídos de cópia externa; instalados em dois venvs externos com `--no-index --no-deps --no-build-isolation --no-compile` |
| wheel (emenda) | 99 entradas, 290.600 bytes, SHA-256 `cc2d0c1fa88217474edf6d161c6f402900e6de76a29602008b43350fcc6a25ed` |
| sdist (emenda) | 124 entradas, 247.695 bytes, SHA-256 `974b57bf0b886c0fe1213c2a8f7d179b43f02a6447dae2112627836c84123b88` |
| conteúdo proibido nas distribuições | nenhum `frontend/`, `tests/`, `docs/`, capturas, `.d.ts`, sourcemap ou link |
| sondagem instalada da Fase 8 | wheel e sdist aprovados (emenda: 11 s cada; `-I`, PATH só System32, sem Node) |
| sondagem instalada do console v2 | wheel e sdist aprovados |
| contraprovas de isolamento | sem `-I`, Node no PATH e site errado: recusados nos dois pacotes |
| navegador contra pacote instalado | emenda: wheel 24/24 (264 s) e sdist 24/24 (235 s): console e pacote nos três engines |
| suíte Python integral, sem deselect, PG 16.15 | **4.157 testes: 4.149 aprovados, 0 falhas, 0 erros, 8 skips** (emenda: 628,4 s) |
| Ruff check / format | aprovados; 174 arquivos |
| mypy strict (`src` + `tests`) | aprovado; 174 arquivos |
| `git diff --check` (com arquivos novos) | aprovado |

Os 8 skips são os condicionais de POSIX já registrados (quatro de `fsync` de
diretório, três de bits de modo e um de `fsync` do filesystem). Nenhum por DSN.

Acessibilidade medida no navegador (três engines): 320, 640 (equivalente a 200%
de 1280) e 1280 CSS px sem rolagem horizontal no Painel, na lista, no detalhe e
no protótipo; transições zeradas com `prefers-reduced-motion`; contraste mínimo
≥ 4,5 em textos visíveis nos temas claro e escuro; tema do sistema aplicado sem
storage; teclado alcança todas as entradas e devolve o foco aos títulos; abas
por setas/Home/End.

## 6. Capturas de referência

57 PNGs em `docs/ux-v2/` (2,6 MB, após o refinamento da seção 8).

- Chromium, claro e escuro, a 1280 e a 320 px: entrada, painel, lista, busca
  sem resultado, detalhe (visão geral, conexão, masking, limites), protótipo
  (início e revisão) e Política v1. A 320 px há também o menu aberto.
- Firefox e WebKit a 1280 px: entrada, painel e lista.
- Estados: vazio, catálogo desligado e catálogo bloqueado a 1280 px; desligado
  e bloqueado também a 320 px.
- Conjunto "antes" em `docs/ux-v2/antes/`. Dados fictícios de fixture; nenhum token ou dado
real. **Precisavam de aprovação antes de qualquer Etapa 6; foram aprovadas
pelo usuário em 2026-09-28 (seção 13).**

## 7. Limitações e riscos

- O limite pós-conexão da D-090 continua aberto e bloqueia a ativação da v2 pelo
  operador (Etapa 7); a v2 segue ativável só pelo composition root.
- A contagem mínima de contraste é automática sobre textos visíveis; não
  substitui a revisão humana das capturas.
- O Playwright 1.63 não acompanha BFCache nativo em Firefox/WebKit; a prova
  nativa continua só no Chromium, como na Fase 8.
- Busca e filtros são locais à página, sem paginação; listas muito grandes não
  foram medidas.
- O ramo POSIX do teste de neto órfão da Etapa 4 segue sem execução neste host.
- `last_test` continua sempre "Nunca verificado" (D-091).

## 8. Refinamento visual (emenda local da Etapa 5)

Pedido: refinar só a apresentação, sem Etapa 6, sem push e sem mudar
funcionalidade, contrato, chamada, vocabulário de wire ou superfície de segurança.
Nenhum framework nem dependência entrou.

### Antes → depois

| problema | antes | depois |
|---|---|---|
| navegação a 320 px | nove entradas empilhadas; o título do Painel começava perto de 870 px, fora da primeira tela | botão de divulgação `Menu: <tela atual>` (`aria-expanded`, `aria-controls`) fechado por padrão; o título começa perto de 300 px |
| hierarquia do Painel | nove métricas de mesmo peso | dois sinais de saúde com texto próprio para cada estado (`✓ Catálogo disponível`, `✓ Escritas liberadas` / `✕ … bloqueadas até reinício`), três métricas principais e quatro detalhes compactos |
| avisos | dois parágrafos longos | duas linhas curtas; não afirmam proteção pós-conexão (D-090 segue aberto) |
| erros no painel | texto cinza repetido | caixa com tom (informação/atenção); o texto de status não mudou |
| tabela | cabeçalhos quebravam no meio da palavra; legenda repetia o título | cabeçalhos sem quebra; legenda só para leitor de tela |
| porta | `5.432` | `5432` |

O conjunto "antes" (5 capturas) fica em `docs/ux-v2/antes/`.

### Acessibilidade do menu

- A navegação continua sendo **um** landmark `nav` no DOM. Em telas estreitas
  ela é ocultada por CSS até ser aberta. Nada fica fora da árvore de
  acessibilidade quando o menu está aberto, e o botão nomeia a tela atual.
- Abrir o menu leva o foco à primeira entrada. `Esc` fecha e devolve o foco ao
  botão. Escolher uma entrada fecha o menu e leva o foco ao título, como antes.
  A partir de 48rem a navegação fica sempre visível e o botão some.
- Setas, chevrons e marcadores são desenhados com CSS (`content:""`). Um glifo
  em `content` entra no nome acessível: `Voltar para a lista` virava
  `← Voltar para a lista`, e `Menu: Painel ▾` quebrava as buscas por nome exato.
  Os testes pegaram isso.

### Prova

- Um teste novo no navegador, `console: narrow screens show content first and
  keep a labelled, keyboard-operable menu`, roda nos três engines. A 320×640 ele
  verifica:
  - menu fechado e navegação oculta;
  - título dentro dos primeiros 60% da tela;
  - `Enter` abre o menu e põe o foco dentro dele;
  - `Esc` fecha e devolve o foco;
  - uma escolha leva o foco ao título e fecha o menu.

  A 1280 px, verifica que a navegação aparece e o botão some.
- O seletor de contraste AA passou a incluir `li`, `.flag` e os botões da
  barra.
- Os testes da Fase 8 a 320 px abrem o menu antes de cada entrada v1. Só o
  caminho até o botão mudou; as asserções são as mesmas.

### Gates do refinamento

| gate | resultado |
|---|---|
| typecheck | aprovado |
| testes Node | **271/271** |
| build determinístico | dois builds com hashes idênticos; `ui.css` 10.312 bytes, `ui.js` 150.197, `presentation.json` 57.196 |
| inspeção pública | limpa |
| navegador, checkout, três engines, PG 16 | **216 testes (72 por engine)**. Na matriz integral: 215 aprovados e 1 `timedOut` no Firefox. O teste que expirou foi `batches.spec.js › two tabs reorder…`, um fluxo v1 que abre uma segunda aba e não toca a v2. Isolado, passou 3/3 em ≈ 40 s, com orçamento de 60 s. O projeto Firefox inteiro foi reexecutado: **72/72**, 0 falhas |
| Ruff / format / mypy strict | aprovados; 174 arquivos |
| `git diff --check` | aprovado |

Os gates de pacote e da suíte Python estão na tabela da seção 5, atualizada com
os números desta emenda.

### Limitações

- Não há aprovação estética automática. As capturas aguardavam aprovação
  explícita do usuário; ela foi dada em 2026-09-28 (seção 13).
- Com erro, o texto de status continua acima do painel, e a caixa de tom dentro
  do painel repete a mensagem. Unificar os dois exigiria mudar o contrato de
  status, o que ficou fora deste refinamento.
- Sem JavaScript não há menu. Isso não é regressão: a UI inteira já depende de
  JavaScript.

## 9. Legibilidade de Datasource/Masking (2026-09-25)

Refinamento solicitado depois da Etapa 5: o detalhe de Masking deixou de
mostrar objetos de configuração crus. Regras e exceções agora aparecem em
cartões numerados, na ordem recebida, com o padrão em destaque, rótulos em
português para correspondência, sensibilidade a maiúsculas/minúsculas,
transformação e parâmetros, além de texto explícito sobre a prioridade das
exceções. A estrutura continua somente leitura; valores desconhecidos são
exibidos como texto, sem descarte silencioso. A aba SQL distingue listas
adicionais da política padrão e explica a lista vazia. A conexão também
explica quando não há hosts adicionais autorizados. A aba Limites já
distinguia valores efetivos dos configurados e não foi alterada.

O vocabulário permanece na apresentação privada. Só o selo `console` da Etapa
5 foi atualizado em `test_phase8_final_inventory.py`; os selos da v1, modelos
e chamadas v2 permaneceram idênticos. Não entraram rotas, escritas,
dependências, PGWire nem funcionalidades de etapas seguintes.

Validação desta alteração: 271/271 testes Node; testes Python direcionados de
UI e inventário aprovados; Ruff, format e mypy strict em `src tests` aprovados
(174 arquivos); build repetido com hashes idênticos para quatro recursos;
capturas sintéticas em Chromium, Firefox e WebKit (61 imagens), com asserções
em desktop e 320 px para prioridade, três cartões, nomes legíveis e vazio de
SQL. As capturas de Masking e Conexão foram atualizadas e as de SQL foram
adicionadas; as demais, que só variaram por horário de leitura, foram
restauradas. Não houve execução da matriz de navegador com PostgreSQL real
nesta alteração: `MASKGW_TEST_DSN` não está definido neste host. A validação
visual não substitui essa matriz antes de publicação.

## 10. Detalhe v2 agrupado e estados legíveis (2026-09-25, sem commit)

Pedido: a Visão geral do datasource era uma lista longa de rótulos e valores,
difícil de interpretar, principalmente a 320 px. As outras superfícies v2 foram
revisadas, e só as que repetiam esse padrão foram ajustadas. Trabalho feito
sobre o refinamento de Masking/SQL/Conexão da seção 9, que ainda não tinha
commit e foi preservado. Decisão em D-101.

### Antes → depois

| superfície | antes | depois |
|---|---|---|
| Visão geral | nove linhas iguais; o nome repetia o título; "Nunca verificado" em texto simples | quatro grupos com título e nota curta: Identidade, Estado no Gateway, Atividade do runtime e Última verificação de conexão. O título segue o nome lido e o nome não se repete. Estados aparecem como pílulas com glifo e texto; "Nunca verificado" é neutro (○), nem falha nem sucesso; sem geração aparece "Nenhuma" |
| Conexão | dez linhas; "✕ Não" para permissões recusadas, que são o estado seguro | quatro grupos: Destino, TLS, Credencial e Destinos aceitos. Identificadores em fonte mono. Permissões aparecem como "Permitido"/"Recusado" neutros, com nota que explica a regra real de destino (rede privada aceita, loopback com permissão, endereço público com permissão e host na lista) |
| Limites | efetivos e configurados misturados | "Aplicado às consultas" em métricas, com a regra do valor efetivo (o menor entre o datasource e a política, como em `_effective`/D-088), e "Configurado no datasource" |
| SQL | funções e limites da política misturados | grupos Funções e Limites da política, com nota que liga os limites aos efetivos |
| lista | "✓ Sim"/"✕ Não"; a 320 px, seis blocos empilhados por item; alias quebrado no desktop | "Não" neutro; "Nunca verificado" neutro sem quebra; alias em fonte mono sem quebra no desktop. A 320 px o nome vira o título do cartão, com alias/revisão e habilitado/publicado em pares |
| Painel | cor dos sinais inferida da ordem das frases; "Não informado" quebrava no meio ("informad/o") a 320 px | tom explícito (achado I1 da revisão anterior); texto vazio em tamanho legível; números das métricas sem quebra ("20/0" em Limites corrigido) |
| protótipo | — | inalterado: já deixava claro que nada é salvo nem testado |

Mantidos de propósito:
- Masking: os cartões da seção 9 já resolviam o problema;
- o protótipo;
- as unidades em ms nos rótulos;
- a quebra das abas em duas linhas a 320 px;
- o comportamento, as chamadas e o foco.

Nenhum campo foi escondido: a validação exige que cada item da aba esteja em um
e só um grupo, e o renderizador exibe qualquer item fora de grupo.

### Capturas

- 69 PNGs em `docs/ux-v2/`, dos quais 8 são novos:
  - `05b-detalhe-desabilitado` (datasource desabilitado e não publicado, estados neutros) em claro e escuro, a 1280 e a 320 px;
  - `firefox-` e `webkit-light-1280-05-detalhe-visao`;
  - `chromium-estado-painel-bloqueado`, a 1280 e a 320 px.
- 30 mudaram de verdade. As que diferiam só pelo horário de leitura (busca vazia, Masking, Política v1 e estado vazio) foram devolvidas à versão anterior.
- Critério: comparação pixel a pixel no Chromium fixado; imagens cuja diferença ficava só na linha de status foram restauradas.
- A ferramenta de captura verifica os grupos, a ausência de "Nome" repetido, "Nunca verificado" neutro, os estados neutros do desabilitado e os dois sinais de alerta do Painel bloqueado.

### Gates

| gate | resultado |
|---|---|
| build determinístico e inspeção pública | aprovados. `ui.js` 158.180, `ui.css` 13.301 e `presentation.json` 62.660 bytes; `index.html` e CSP inalterados |
| typecheck (inclui `--strict` no bundle) | aprovado |
| testes Node | **279/279** (271 + 8 contraexemplos: grupo que esconde ou duplica item, membro ou chave desconhecidos, tom ou exibição desconhecidos, título numérico ou fora do modelo) |
| Python direcionado | **108/108**: inventário, recursos e o novo `test_admin_ui_console_groups.py` (os mesmos contraexemplos no validador Python) |
| selos | só `console` mudou. `format`, os modelos v2 (`models[110:]`) e as chamadas v2 (`calls[19:]`) mantêm os seus hashes, e as seções v1 continuam iguais às aprovadas na Etapa 8 |
| navegador, três engines, PostgreSQL 16.15 descartável | **216 testes**. Na matriz integral, 215 aprovados e 1 falha intermitente no WebKit ('wide shows nav'). O teste lia a visibilidade logo após redimensionar a viewport, antes de o WebKit aplicar a media query; passou a esperar o estado com `expect.poll`, sem mudar o que é verificado. Depois disso: 20/20 repetições isoladas, projeto WebKit inteiro 72/72 e `console.spec.js` 14/14 no Chromium e no Firefox |
| suíte Python integral com PostgreSQL 16.15 descartável | **4.167 testes: 0 falhas, 0 erros, 8 skips** (os condicionais de POSIX já registrados); 615 s |
| Ruff / format / mypy strict | aprovados; 175 arquivos |
| `git diff --check` e arquivo novo | aprovados |

O contraste AA passou a ser medido também nas cinco abas do detalhe, nos dois
temas, incluindo `h3`, `code`, abas e pílulas. A falta de rolagem horizontal é
verificada em todas as abas, a 320, 640 e 1280 px.

Não executado: o gate de pacote isolado (wheel/sdist instalados e navegador
contra o pacote). A mudança não toca empacotamento, mas os bytes dos recursos
mudaram, então esse gate deve ser repetido antes de qualquer commit. O
PostgreSQL usado foi um contêiner descartável `postgres:16-alpine` só em
`127.0.0.1`, removido ao final; nenhum banco existente foi usado.

## 11. Política v1 legível (2026-09-28, sem commit)

Pedido: a Visão geral da Política v1 exibia uma árvore crua com nomes internos
em inglês, e as demais leituras v1 tinham o mesmo problema. O pedido autorizou
mudar **só a apresentação** da v1. Contratos, modelos, chamadas, permissões,
regras de masking e fluxos de escrita continuam congelados. Decisão em D-102.

### O que mudou e o que não mudou

- **Não mudou (prova por igualdade com o HEAD `5077ce1`)**:
  - `views`, `editors`, `bindings`, `messages` e `format`;
  - **todos** os modelos (147) e **todas** as chamadas (23).

  O teste de selos da Etapa 8 (`APPROVED`, 7 seções) passa sem alteração.
  Formulários, rótulos de formulário, confirmações, validação e escrita são os
  mesmos, e os botões do editor v1 (Validar documento, Adoção explícita, Criar,
  Item N · Editar/Excluir) continuam no mesmo lugar.
- **Mudou**:
  - `console.pages`, a apresentação das seis leituras v1 em grupos, com rótulos
    e notas em português;
  - o selo `console` da Etapa 5 e o hash de `presentation.json`;
  - no renderizador, a leitura v1 usa a página quando ela existe; sem página, o
    comportamento anterior é mantido;
  - listas passaram a aceitar texto declarado por item e o estilo "ordered";
    dentro dos cartões, os campos seguem a ordem declarada;
  - CSS: lista numerada; grupos que não esticam até a altura do vizinho, o que
    também afeta as abas v2 (caixa Credencial menor); grupos com cartões de regra
    ocupam a largura toda.
- **Garantia de que nada foi omitido nem acrescentado**:
  - o validador Python e o checker público exigem que toda folha sob os
    controles `read` de cada vista seja exibida;
  - e que nenhum campo fora desses controles apareça.
  Contraexemplos em `tests/test_admin_ui_console_groups.py` e em
  `frontend/test/surface.test.js`.

### Antes → depois

| vista | antes (`docs/ux-v2/antes/v1/`) | depois |
|---|---|---|
| Visão geral | `adopted`, `counters`, `revision`, `runtime` e `secrets` com chaves internas | Configuração em uso (adoção, com a explicação real de "não adotada"), Atividade desde o início do processo (métricas, com a regra de contagem), Runtime (versão anterior em drenagem) e Segredos (só a situação; HMAC ausente é neutro) |
| Configuração | documento inteiro como árvore | Estado, Regras de masking e Exceções em cartões, Limites do banco e SQL |
| Regras / Exceções | lista de chaves cruas, com ID como primeira linha | cartões "Regra N"/"Exceção N" com padrão em destaque, correspondência, maiúsculas/minúsculas, transformação, parâmetros, posição e identificador ("Ainda sem ID: a adoção atribui" quando não adotada) |
| Banco | `Revision` e `Limites declarados` em árvore | métricas com a nota de aplicação pelo PostgreSQL |
| Política SQL | onze blocos "Proteção efetiva: …" | Como cada coluna é tratada (ordem do pipeline em português), Validação do SQL (as quatro regras traduzidas), Funções e relações, Sessão no PostgreSQL e Edição |

Capturas: 24 novas, em Chromium claro e escuro a 1280 e a 320 px:
`12-v1-configuracao`, `13-v1-regras`, `14-v1-excecoes`, `15-v1-banco`,
`16-v1-politica-sql` e `chromium-estado-v1-nao-adotada-{visao,regras}`
(1280 e 320). Mais 16 alteradas (`11-politica-v1` e as abas v2 afetadas pelo
alinhamento). O conjunto "antes" dessas vistas está em `docs/ux-v2/antes/v1/`
(28 imagens). As imagens que diferiam só pelo horário, e as do Firefox que mudaram
por ruído de renderização em telas que o CSS novo não alcança, voltaram à
versão anterior. A fixture sintética da v1 fica em `screenshots.js`: coerente
(uma revisão em todas as leituras) e fictícia, nas variantes adotada e não
adotada.

### Achados durante a revisão

- Na vista Exceções, o título `h2` e o grupo `h3` tinham o mesmo nome. Isso é um
  defeito de acessibilidade (dois cabeçalhos iguais para leitor de tela) e fazia
  a busca exata pelo título falhar. O grupo virou "Exceções cadastradas", e há
  teste que exige título único e nenhum grupo com o nome da própria vista.
- No WebKit, o teste novo esperava 60 s depois de redimensionar a viewport. É a
  mesma corrida de media query da seção 10: o teste agora espera o layout
  correspondente e passou a levar 12,5 s.
- `reading.spec.js › loading, empty…` esperava o texto genérico "Lista vazia.".
  A leitura de regras vazia agora diz "Nenhuma regra de mascaramento
  cadastrada.". O teste continua exigindo o texto exato e exatamente uma
  ocorrência, depois do mesmo fluxo de erro e nova tentativa.

### Gates (seção 11)

| gate | resultado |
|---|---|
| build determinístico | dois builds com hashes idênticos: 4 recursos, âncora, `presentation.json` e `protocol-schema.json` privados |
| inspeção pública | limpa (os nomes novos passam pelo vocabulário v1 por substring e v2 por token) |
| typecheck | aprovado |
| testes Node | **285/285** (+6 contraexemplos de `console.pages`) |
| Python direcionado | **116/116** (inventário com `APPROVED` intacto, recursos e grupos/páginas) |
| suíte Python integral, PostgreSQL 16.15 descartável | **4.175 testes: 0 falhas, 0 erros, 8 skips POSIX**; 639 s |
| navegador, três engines, checkout | matriz integral: 215/219. As 4 falhas eram os dois pontos acima (texto esperado em `reading.spec.js` nos três engines; corrida no WebKit no teste novo). Depois das correções, `console.spec.js` + `reading.spec.js` deram **75/75** nos três engines; os demais arquivos não mudaram depois da matriz |
| wheel / sdist | 99 e 124 entradas; wheel SHA-256 `657b5f17d4293c024628b800788dbb9f465e1c6b34bd25062d282efd91ee48c5`; sdist SHA-256 `496dbfeacbcea89f2b8f8ce404f820bbfc6b753f9c01972d581f6fab50711313`; sem `frontend/`, `tests/`, `docs/`, capturas, `.codex` ou links |
| sondagens instaladas | Fase 8 e console v2 aprovadas nos dois pacotes (`-I`, PATH só System32) |
| contraprovas de isolamento | sem `-I`, Node no PATH e site errado: recusados nos dois pacotes |
| navegador contra o pacote instalado | wheel **27/27** e sdist **27/27** (console e pacote nos três engines) |
| Ruff, format e mypy strict | aprovados; 175 arquivos |
| `git diff --check` e arquivo novo | aprovados |

O teste novo de navegador cobre as seis vistas v1 nos dois temas, a 320 e a
1280 px, e verifica:
- grupos na ordem declarada;
- título único, com foco depois da navegação;
- ausência de nomes internos crus;
- ausência dos segredos reais do harness (chave HMAC e senha/DSN do
  PostgreSQL descartável);
- segredos só como "Configurado"/"Ausente";
- contraste AA ≥ 4,5 e ausência de rolagem horizontal;
- somente GET.

Limitações:
- a fixture sintética das capturas não substitui a revisão humana;
- o Firefox teve ruído de renderização entre execuções nas telas de entrada,
  Painel e lista, que não foram afetadas por esta mudança; essas capturas
  voltaram à versão anterior;
- ~~o editor v1 continua anexando "Item N · Editar/Excluir" abaixo dos cartões,
  sem ligação visual com o cartão correspondente~~. **Resolvida na seção 12**:
  cada conjunto de ações fica dentro do cartão do item com o mesmo ID, sem mudar
  handlers, IDs, ordem, confirmações, validações nem escrita.

O PostgreSQL foi um contêiner descartável `postgres:16-alpine`, só em
`127.0.0.1`, removido ao final. O Docker Desktop estava parado: foi iniciado
para os testes e parado de novo.

## 12. Ações de cada item dentro do próprio cartão (2026-09-28, sem commit)

Pedido: na vista Regras, e também em Exceções, os botões Editar e Excluir
apareciam em linhas "Item N" separadas dos cartões "Regra N"/"Exceção N". O
ajuste associa visualmente cada conjunto ao item certo. Handlers, IDs, ordem,
confirmações, validações e escrita não mudaram.

### Como a associação é feita

- `workbench.attach` recebe uma função opcional, `slot`. Ela recebe a
  identidade que os botões **já** usavam (capturada no fechamento do handler,
  como antes) e devolve o cartão que exibe essa **mesma** identidade. Os botões
  são os mesmos objetos, com os mesmos handlers, na mesma ordem. Com cartão, vão
  para um grupo `role="group"` com nome "Ações: Regra N"; sem cartão, ficam na
  linha "Item N" de antes.
- O mapa identidade → cartão é refeito a cada leitura, a partir do mesmo valor
  exibido. A associação é **só por igualdade de ID**, nunca por posição. Uma
  identidade repetida entre cartões marca a ambiguidade e não recebe ação.
- Na prática, uma identidade repetida nem chega à tela: o leitor da Fase 8 já
  recusa a lista (binding `identity`), e a leitura fica "indisponível", sem
  cartões e sem botões. A proteção em `screen.js` é uma segunda camada.
- Apresentação: a chave de identidade é declarada em `console.pages` pelo texto
  `@identity: id` nas palavras de regras e exceções da v1. Só o selo `console`
  muda; as sete seções da Etapa 8 continuam iguais ao HEAD `5077ce1`.

### Teste adversarial

`batches.spec.js › item actions stay with their own card across reorder, edit
and removal` roda nos três navegadores e usa a fixture com duas regras de
**mesmo padrão**, diferentes só no ID e no valor substituto:

1. cada cartão tem exatamente um grupo "Ações: Regra N" e um Editar e um
   Excluir; não sobra linha "Item N" nem ação avulsa;
2. o Editar de cada cartão abre o formulário com o valor daquele cartão;
3. depois de reordenar, as identidades acompanham os cartões, e o Editar
   continua abrindo o item certo;
4. editar o primeiro cartão gera **um** `PUT` cujo caminho é exatamente
   `/admin/v1/rules/<ID exibido nesse cartão>`, e só esse cartão muda;
5. excluir o segundo cartão gera **um** `DELETE` com o ID exibido nesse cartão;
   o outro cartão fica intacto e continua editável;
6. em Exceções, a ação do cartão abre a exceção "keep";
7. uma resposta com ID repetido é recusada: nenhum cartão, nenhum botão,
   nenhuma escrita.

### Capturas

Mudaram só as 8 imagens de Regras e Exceções (`13-v1-regras` e
`14-v1-excecoes`, claro e escuro, 1280 e 320 px). As demais diferiam só pelo
horário, ou por ruído de renderização do Firefox em telas que esta mudança não
alcança, e voltaram à versão anterior.

`CLAUDE.md` e `docs/HANDOFF.md` citam 102 decisões (D-001 a D-102), porque
D-101 e D-102 estão registradas em `docs/DECISIONS.md`. O `HANDOFF.md` foi
corrigido no fechamento editorial seguinte.

### Gates (seção 12, sobre o resultado final)

| gate | resultado |
|---|---|
| build determinístico e inspeção pública | 8 arquivos com hashes idênticos em dois builds; artefatos públicos limpos |
| typecheck | aprovado |
| testes Node | **285/285** |
| Python direcionado | **116/116** (`APPROVED` da Etapa 8 intacto; só o selo `console` mudou) |
| suíte Python integral, PostgreSQL 16.15 descartável | **4.175 testes: 0 falhas, 0 erros, 8 skips POSIX**; 568 s |
| **matriz completa, três engines, checkout** | **222/222** (74 por engine), 0 falhas, timeouts ou retries; 2.163 s |
| wheel / sdist | 99 e 124 entradas; wheel SHA-256 `7a7b388c4491727892dbf3ac911669ed8488cd89315fa3fc4157f40558874913`; sdist SHA-256 `4f43052366a0bc401e17dcabdc9c2a263963fb759a259fcfc3cca706766a0a4a`; nada proibido, sem links |
| sondagens instaladas | Fase 8 e console v2 aprovadas nos dois pacotes |
| contraprovas de isolamento | sem `-I`, Node no PATH e site errado: recusados nos dois pacotes |
| navegador contra o pacote instalado | wheel e sdist: **27/27** (console e pacote) e **3/3** no teste adversarial das ações, nos três engines |
| Ruff, format e mypy strict | aprovados; 175 arquivos |
| `git diff --check` | aprovado |

O PostgreSQL foi um contêiner descartável `postgres:16-alpine`, só em
`127.0.0.1`, removido ao final. O Docker Desktop foi iniciado para os testes e
parado de novo.

## 13. Aprovação e fechamento (2026-09-28)

O usuário aprovou explicitamente, em 2026-09-28, o refinamento visual das
seções 8 a 12, as capturas de `docs/ux-v2/` e as decisões D-101 e D-102. A
Etapa 6 e as posteriores continuam sem autorização. Nada foi publicado: não
houve push.

Atribuição dos resultados:
- os gates da seção 12 (matriz completa 222/222, wheel/sdist instalados, suíte
  Python integral 4.175, Node 285/285, build determinístico) foram medidos sobre
  o resultado funcional final;
- depois deles mudaram só documentos (`HANDOFF.md`, `DECISIONS.md`, esta
  validação e o estado de aprovação em `CLAUDE.md`, `AGENTS.md` e na matriz
  de rastreabilidade), sem alteração de código, testes, recursos ou capturas;
  por isso as suítes não foram repetidas;
- o refinamento completo foi registrado num novo commit local, depois de
  `5077ce1`, sem emenda nem push.
