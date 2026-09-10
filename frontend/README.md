# Ferramentas privadas da UI administrativa — Etapa 2

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

`src/protocol.js` é somente um verificador declarativo; não contém DOM, fetch,
sessão ou transporte. A função pública `check` aplica o protocolo fixado no
asset, e `digest` identifica a apresentação estática correspondente. A leitura
do recurso privado e a conferência Web Crypto antes da interpretação pertencem
às etapas posteriores; não existem nesta fundação. A Etapa 3 acrescenta a flag
e a chamada Python antes do startup; ainda não há entrega HTTP de recursos.

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

Views, editores e controles são descrições estáticas, ainda sem renderização.
Condições só descrevem presença/igualdade/escolha/booleano. Projeções descrevem
copy/object/list/omit/insert/replace/remove/permute com fontes fechadas base ou
draft, paths vetoriais e destino vetorial; não são executadas nesta etapa.
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
