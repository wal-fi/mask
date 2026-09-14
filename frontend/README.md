# Ferramentas privadas da UI administrativa — Etapa 6

Node 24.20.0, npm 11.19.0, TypeScript 5.9.3 e Playwright 1.63.0.
`@types/node` 24.0.0 é uma dependência exclusivamente de declarações para
verificar também ferramentas e testes Node. Não há biblioteca de runtime.
Todas as dependências são exatas; o lock v3 fixa transitivas e integridade.

Executar nesta pasta, com o Node/npm aprovados no PATH e a `.venv` Python
existente na raiz:

```text
npm ci --ignore-scripts
npm run typecheck
npm test
npm run build
npm run inspect
```

`.npmrc` exige engines e desabilita scripts de instalação. O build confere
Node, gera contratos/vocabulário das fontes atuais, verifica tipos, gera e
valida a apresentação, monta um ESM sem bundler, verifica bytes/tipos finais
e grava manifesto/âncoras. Não lê configuração, secrets ou estado instalado.
Dois builds completos devem produzir os mesmos bytes. O npm não participa do
startup nem da construção de wheel/sdist: os recursos já estão embarcados.

`src/protocol.js` continua como verificador declarativo sem DOM. A função
pública `check` aplica o protocolo e `digest` ancora a apresentação estática.
`src/transport.js` conserva a credencial em closure privada, autentica e verifica
apresentação/hash/gramática e suporta encerramento/cancelamento. `reader.js`
interpreta modelos privados para validar DTOs fechados, inteiros seguros,
identidades/ordem e revisions coerentes antes do estado. `screen.js` monta o
login explícito e seis vistas somente leitura a partir da apresentação. Não
faz rede administrativa antes da entrada, não invoca check/escritas, não usa
URL/histórico ou stores. Logout/401/pagehide/pageshow/BFCache descartam estado,
DOM, metadados e token; cancelamento e geração bloqueiam respostas tardias.
Status é lido a cada 15 s somente visível, sem sobreposição; falha suspende
polling e retry é manual. O transporte check da Etapa 4 permanece apenas para
compatibilidade do seu gate, sem uso pelas telas. Etapas 7–9 não iniciadas.
A Etapa 3 valida bytes antes do bind; a fronteira HTTP da Etapa 4 não muda.

Para o gate acumulado da Etapa 6, definir `MASKGW_TEST_DSN` para PostgreSQL 16 real
e executar `npm run test:browser`. Instalar previamente os três binários pelo
Playwright fixado (`playwright install chromium firefox webkit`), sem atualizar
versões. Chromium 153.0.8010.12/revisão 1243, Firefox 155.0/1543 e WebKit 26.6/2359.
O harness usa o composition root real, token aleatório apenas em memória/ambiente
do processo e config descartável. Inspeciona logs sem gravar registros, fecha os
contextos antes de relatar falhas e usa reporter de categorias fixas. Trace,
HAR, vídeo e screenshot não são habilitados. `MASKGW_BROWSER_REDIRECT` e
`MASKGW_BROWSER_CSRF` existem somente no harness privado, nunca no produto.

`private/` contém tipos dos onze contratos e a união das dez escritas UI,
schemas derivados, vocabulário e autoria de apresentação. Nada dessa pasta,
fixtures, ferramentas, sourcemaps ou declarações é distribuído no wheel/sdist.
Somente os quatro recursos finais, manifesto interno e módulos Python de
validação/âncora entram no pacote. O `.gitattributes` preserva LF para que um
checkout Windows não altere os bytes protegidos por hash.

## Protocolo fechado

A definição de estrutura está em `maskgw.admin.ui.protocol`, exportada como
schema somente para o build. Python e JavaScript têm verificações independentes
de grafo, destinos, referências, defaults, limites e chaves perigosas. O JS não
incorpora o catálogo administrativo: a âncora privada e o validador Python
fecham exatamente as 19 chamadas e seus modelos. Nenhum exemplo de instalação
é colocado na apresentação.

Modelos são planos e referenciados por IDs opacos: string (limites, prefixo e
alfabeto do sufixo), inteiro seguro, booleano, enum, objeto fechado, lista,
nullable ou união discriminada. Campos declaram referência, obrigatoriedade e
default escalar, quando aplicável. Defaults nulos representam ausência de um
default de formulário. Ciclos ou caminhos ausentes invalidam tudo. O grafo é
memoizado para não expandir repetidamente subgrafos compartilhados.

Views, editores e controles são descrições estáticas; somente as seis vistas
de leitura são renderizadas nesta etapa.
Condições só descrevem presença/igualdade/escolha/booleano. Projeções descrevem
copy/object/list/omit/insert/replace/remove/permute com fontes fechadas base ou
draft, paths vetoriais e destino vetorial. A Etapa 6 executa seleção/cópia e
construção de objetos/listas a partir dos modelos privados; operações de
edição de candidato/formulários permanecem nos marcos seguintes.
Não há fonte token, ambiente, função ou código. Não existe merge genérico.
As ligações usam papéis abstratos; `consent` representa adoção sem expor o
literal privado da operação. Nenhuma exceção lexical foi adicionada à lista
pública da especificação para contornar testes.

Mensagens privadas são texto fixo. Strings com `__proto__`, `constructor` ou
`prototype` continuam sendo dados textuais; somente chaves/segmentos estruturais
são proibidos. O recurso privado é validado contra o catálogo e fingerprint
dos modelos no Python; a integridade dos bytes é ancorada no manifesto.
Isso detecta incompatibilidade/corrupção, não um pacote integralmente comprometido.

O verificador público examina bytes, literais e identificadores JavaScript
decodificados, concatenações constantes, entidades HTML e escapes CSS. Recusa
mecanismos de reconstrução executável; não alega prova contra inferência geral.
O vocabulário vem de schemas, enums, rotas, registry e proteções existentes,
subtraindo exclusivamente os dez nomes compartilhados normativos.

## Componentes e lifecycle

`browser/reading.spec.js` combina leitura real e transporte controlado para
falhas, DTOs hostis e relógio/visibilidade; `browser/lifecycle.spec.js` usa uma
página-fixture local com os mesmos bytes do componente. Os fixtures não entram
no pacote ou nas rotas do produto. O harness READ_ONLY exige zero escrita,
audit administrativo ou mudança de arquivo/snapshot/contador. PostgreSQL
indisponível após startup e API encerrada são injetados no harness privado.

Playwright 1.63.0 documenta nos tipos de `Page.goBack` que BFCache não é suportado
pelo seu acompanhamento de navegação e fica desligado por padrão. Os três
engines executam cleanup com PageTransitionEvent persisted=true e navegação
real/reload. Uma prova adicional usa Chromium completo do mesmo pin, habilita
BFCache removendo somente o argumento que o desliga e observa restauração
nativa por CDP, sem usar goBack do Playwright. O fixture é elegível a cache;
a política no-store do produto permanece intacta. Não alegar restauração
nativa do Firefox/WebKit automatizados. Detalhes, resultados e limitações em
`docs/PHASE-8-STAGE-5-VALIDATION.md` na raiz.

## Coordenador e transporte granular

`commands.js` recebe somente metadados autenticados, resolve chamada/método/
identidade/modelos e projeta corpo fechado a partir do rascunho e versão-base.
`transport.js` expõe prepare/mutate além das leituras, sem qualquer chamada
implícita. `coordinator.js` expõe load, begin/change, confirm, cancel, reconcile,
review, finish, discard e close; não é instalado por screen e não expõe controles
de escrita. getState/getObservation devolvem referências congeladas.

load é explícito. begin/change conservam o snapshot-base e congelam conteúdo;
confirm revalida o comando e admite uma pendência. Polling durante rascunho
registra uma observação separada; durante pendência é recusado. Conflito só
aceita base nova por review humano; busy só repete por confirm explícito.
Sucesso relê automaticamente; finish exige a releitura. cancel não cancela a
operação no servidor. Desconhecido e durabilidade incerta permitem reconcile,
mas continuam bloqueados para mutação e não têm rollback/retry automático.
Logout/401/pagehide/pageshow limpam o coordenador; respostas antigas são ignoradas.

Testes específicos: test/commands.test.js, test/coordinator.test.js e
browser/coordinator.spec.js. Evidência atual na raiz:
`docs/PHASE-8-STAGE-6-VALIDATION.md`. Não publicar Etapa 6 nem iniciar Etapa 7.
