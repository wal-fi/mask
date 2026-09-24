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
real. **Precisam de aprovação antes de qualquer Etapa 6.**

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

- Não há aprovação estética automática. As 57 capturas aguardam aprovação
  explícita do usuário antes da Etapa 6.
- Com erro, o texto de status continua acima do painel, e a caixa de tom dentro
  do painel repete a mensagem. Unificar os dois exigiria mudar o contrato de
  status, o que ficou fora deste refinamento.
- Sem JavaScript não há menu. Isso não é regressão: a UI inteira já depende de
  JavaScript.
