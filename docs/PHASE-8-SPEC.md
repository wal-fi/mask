# Fase 8 — Front-end · Especificação aprovada

**Estado:** aprovada; Etapa 1 concluída.
**Base:** Fase 7 concluída no commit `27d92bd580875e9eb2abb04db102eb98af2054fe`.

## 1. Arquitetura recomendada e justificativa

### 1.1. Conflito arquitetural

A fronteira administrativa atual rejeita qualquer presença de `Origin` ou `Referer`, inclusive de mesma origem. Não possui CORS, HTML ou assets, mantém inventário fechado de rotas e aceita o token exclusivamente em `Authorization`.

Um navegador real normalmente envia `Origin` em escritas. Portanto, acrescentar HTML sem mudar essa fronteira não produz uma UI funcional.

A Fase 8 propõe uma alteração explícita e condicionada à ativação da UI: **aceitar somente origens exatamente iguais à origem administrativa da requisição**, mantendo origens externas bloqueadas e CORS ausente.

### 1.2. Recomendação

**UI embarcada no pacote Python, servida pelo mesmo processo, porta e origem da Admin API.**

O navegador acessa exclusivamente a fronteira HTTP administrativa. A UI não acessa diretamente PostgreSQL, filesystem, runtime, Masking Engine ou MCP.

Benefícios:

- um único listener e lifecycle;
- distribuição conjunta de API e UI compatíveis;
- nenhuma necessidade de CORS para chamadas legítimas;
- reutilização dos contratos de concorrência e persistência;
- funcionamento do pacote instalado sem Node ou servidor adicional.

O custo de segurança é explícito: o navegador passa a integrar o plano administrativo privilegiado. XSS pode permitir operações com o token mantido em memória; CSP e renderização textual são obrigatórias, mas não tornam um navegador comprometido confiável.

### 1.3. Ativação

Nova variável: `MASKGW_ADMIN_UI_ENABLED`.

| Valor bruto | Resultado |
|---|---|
| Exatamente `1` | Solicita habilitação |
| Ausente ou string vazia | UI desligada |
| Qualquer outro valor, inclusive `0`, `true`, `yes`, `01`, ` 1` e `1 ` | UI desligada |

A comparação não faz `strip`, conversão de caixa ou interpretação booleana.

O provider atual normaliza espaços. Portanto, **a nova flag não pode usar sua leitura normalizada**. Sua resolução deve receber o valor bruto de uma fonte de settings, com equivalente injetável em testes. Isso não altera a leitura dos secrets nem o comportamento das variáveis existentes.

UI habilitada com Admin API desabilitada:

- falha de startup;
- nenhuma habilitação implícita;
- nenhuma porta, thread HTTP ou sessão MCP disponibilizada;
- saída de processo `1`;
- mensagem externa exatamente `maskgw: falha na inicializacao\n`, em stderr;
- nenhuma causa, valor de variável, caminho ou traceback exposto.

### 1.4. Startup e lifecycle

Ordem obrigatória quando a UI estiver habilitada:

1. Ler as flags e verificar a dependência UI → Admin API.
2. Validar settings administrativos existentes: token, bind e porta.
3. Carregar e validar manifesto e recursos UI, conforme §5.5.
4. Manter os bytes validados em memória imutável.
5. Executar o carregamento, lock, compilação e conexão do runtime existentes.
6. Construir a aplicação HTTP sobre os recursos já validados.
7. Realizar e confirmar o bind.
8. Disponibilizar MCP pelo lifecycle existente.

Falha nos passos 1–4 ocorre antes de adquirir o lock da configuração, conectar ao banco ou abrir a porta.

Fechar a aba não encerra o Gateway. Não abrir navegador automaticamente. Shutdown preserva a ordem existente: interromper admissão de trabalho, aguardar a thread HTTP, fechar runtimes e liberar o lock.

Representações:

- com UI desligada, preservar os `repr` existentes;
- com UI ligada, permitir somente indicação booleana adicional de habilitação;
- nunca incluir token, tamanho do token, manifesto, conteúdo de assets ou dados administrativos;
- não adicionar linha de startup que exponha informações além das mensagens operacionais já permitidas.

### 1.5. Compatibilidade com UI desligada

Com UI desligada:

- não carregar ou validar assets;
- não registrar rotas UI;
- não instalar novos headers de navegador;
- não mudar parsing de Host, política de Origin/Referer, autenticação, erros ou redirecionamento;
- não alterar configuração de proxy headers como efeito desta fase;
- não acrescentar auditoria ou saída de processo.

A superfície da Fase 7 deve ser preservada byte a byte para as mesmas entradas e estado controlado: status, corpo, headers determinísticos e representações. Em testes HTTP reais, o header temporal `Date` deve ser controlado ou comparado separadamente.

## 2. Alternativas avaliadas

| Critério | Mesma origem — recomendada | Processo/porta local separada | Aplicação desktop/nativa |
|---|---|---|---|
| Superfície | Navegador, HTML e assets na origem administrativa | Dois listeners e duas origens | Binário, toolkit e possível IPC |
| Alterações na Fase 7 | Recursos UI e aceitação exata de mesma origem | Aceitação de origem distinta, CORS e preflight | Cliente HTTP nativo pode preservar a fronteira atual |
| CSRF/CORS | Bearer explícito, origem verificada e CORS ausente | Exige controles CSRF além de CORS restrito | Cliente nativo não sofre CSRF clássico; ataques de páginas contra a API continuam relevantes |
| Token | Memória da aba | Memória da aba; maior risco de destino incorreto | Memória do processo |
| Lifecycle | Coordenado pelo bootstrap existente | Coordenar processos, portas e falhas independentes | Coordenar aplicativo e Gateway |
| Build/distribuição | Assets no wheel/sdist | Dois artefatos e procedimento de inicialização | Pacotes por sistema operacional |
| Testes | HTTP, navegador e pacote instalado | Mesmos testes, mais CORS e coordenação | Automação nativa por plataforma e testes HTTP |
| Complexidade | Moderada, com custo adicional do interpretador descrito adiante | Maior sem necessidade funcional nesta fase | Maior em distribuição e manutenção multiplataforma |

A porta separada não é recomendada porque acrescenta CORS e coordenação sem atender a uma necessidade do escopo. `file://` também não é uma alternativa: pode produzir origem opaca.

A aplicação nativa preservaria melhor a fronteira atual, mas introduziria outra frente de distribuição e testes. Um invólucro WebView não elimina automaticamente ameaças do navegador.

## 3. Contrato funcional e apresentação

### 3.1. Objetivo e exclusões

Permitir administração local da configuração já suportada pela Admin API, apresentando corretamente concorrência, aplicação e falhas.

Ficam fora:

- SQL editor, execução de SQL e resultados do banco;
- visualização de schemas/tabelas do PostgreSQL ou funcionalidades de DBA;
- front-end, transporte ou expansão do MCP;
- edição de DSN, credenciais, token e chave HMAC;
- edição de `allowed_pg_functions`, IDs, revision e proteções estruturais;
- reorder de exceptions;
- substituição completa da configuração pela UI;
- endpoints, stores, histórico ou página de auditoria;
- editor YAML/JSON livre, importação/exportação e operações em lote;
- OAuth, RBAC, multiusuário, telemetria e serviços externos;
- TLS, proxy, bind externo, deployment e atualização automática.

### 3.2. Páginas e navegação

Uma entrada HTML, com navegação interna:

| Página | Contrato |
|---|---|
| Entrar | Token, ação Entrar e mensagens genéricas |
| Visão geral | Status administrativo, revision, adoção, runtimes aposentados, contadores e estados dos secrets |
| Configuração | Documento estruturado somente leitura; validar configuração; adoção legada |
| Regras | CRUD granular e reorder dedicado |
| Exceptions | CRUD granular, preservando a ordem atual |
| Database | Timeout e máximo de linhas |
| SQL policy | Negação aditiva e proteções somente leitura |

Formulários e confirmações não criam rotas HTTP de navegação.

A navegação usa estado em memória. URL e histórico não carregam token, IDs selecionados, filtros, padrões, valores, mensagens ou rascunhos. Nesta fase não haverá deep links.

Não há autosave. Abandonar edição alterada exige confirmar descarte ou continuar editando. Reload perde rascunhos e exige novo token.

### 3.3. Status

Usar `/admin/v1/status`:

- `revision` e `adopted`;
- `runtime.revision`;
- `runtime.retired_runtimes_open`;
- `queries_total`;
- `admin_operations_total`;
- secrets exclusivamente como `configured` ou `missing`.

Contadores representam atividade desde o startup. O contador administrativo inclui tentativas que entram na seção crítica; `config:validate` não conta como escrita.

Não apresentar “PostgreSQL saudável” ou “MCP conectado”: o endpoint não fornece essas garantias.

Mostrar última leitura e estados distintos: carregando, respondendo, desatualizado, indisponível e autenticação necessária.

Polling de status a cada 15 segundos apenas com página visível, sem sobreposição. Suspender após falha ou durante escrita pendente; retry manual.

### 3.4. Configuração

A fonte é um snapshot de `/admin/v1/config`.

- Documento declarado separado das proteções efetivas de `/protected`.
- IDs e revisions apenas para leitura.
- Configuração legada mostra identidade ausente, sem inventar IDs.
- Nenhum YAML original, comentário, caminho, backup ou digest.
- Respostas de endpoints diferentes não formam automaticamente um snapshot conjunto.
- Revisões divergentes devem ser identificadas; não combinar conteúdos incompatíveis.

### 3.5. Regras

Campos editáveis:

- `match`;
- `mode`: `contains` ou `exact`;
- `case_sensitive`;
- `transformer`;
- parâmetros admitidos pelo transformer.

Defaults: `contains` e `case_sensitive=false`. Transformer exige escolha explícita.

Preservar exatamente o texto de `match`; não aplicar trim ou normalização silenciosa.

Operações:

| Ação | Contrato |
|---|---|
| Criar | `POST /rules`; inserir no fim por padrão |
| Editar | `PUT /rules/{rule_id}` com conteúdo completo |
| Excluir | `DELETE /rules/{rule_id}` com confirmação |
| Reordenar | `POST /rules:reorder` com permutação completa dos IDs |

Reorder exige revisão e confirmação antes de persistir. “Mover para cima/baixo” funciona por teclado; drag-and-drop é opcional. Cancelar restaura a ordem-base.

A ordem das regras pode alterar a política. Filtros e busca não alteram ordem persistida. Posições exibidas começam em 1; a API usa índice iniciado em 0.

### 3.6. Exceptions

Campos: `match`, `mode` e `case_sensitive`.

Defaults: **`exact` e `case_sensitive=false`**. Não possuem transformer.

- Criar, editar e excluir pelas rotas granulares existentes.
- Preservar a ordem relativa dos itens existentes.
- Criação acrescenta o novo item segundo o contrato atual.
- Edição não muda posição.
- Exclusão remove somente o item.
- Nenhum controle de reorder.
- Nenhum `PUT /config` para reorganização visual.

Exceptions podem permitir valores originais. A confirmação de criação ou ampliação de correspondência deve explicar esse efeito e a correspondência pelo nome autoritativo.

A ordem entre exceptions não muda sua prioridade sobre regras. Se reorder for necessário futuramente, exigirá endpoint granular, operação de auditoria e decisão próprios.

### 3.7. Transformers

Consultar `/transformers` e confrontar o catálogo com as definições de formulário privadas e versionadas.

| Transformer | Parâmetros |
|---|---|
| `md5`, `sha256`, `sha512`, `hmac_sha256` | Nenhum |
| `fixed` | `value`: string |
| `truncate` | `length`: inteiro ≥ 0 |
| `regex` | `pattern`, `replacement`: strings |
| `random` | `strategy`: `digits` ou `alphanumeric`; `preserve_length`: booleano; `length`: inteiro ≥ 0 quando não preservar comprimento |

Em `random`, `length` deve estar ausente quando `preserve_length=true`.

Sem parâmetros arbitrários ou campos de segredo. Transformer desconhecido/incompatível permanece visível em leitura, mas sua edição é bloqueada sem descarte de conteúdo.

Não executar regex em JavaScript e não oferecer preview de transformação.

Orientações contextuais devem preservar os riscos documentados: hashes sem chave em domínios pequenos, prefixos preservados por `truncate`, exceptions amplas e perda de correlação por `random`.

### 3.8. Database e SQL policy

**Database:** `PUT /database`, enviando ambos os campos:

- `statement_timeout_ms`: inteiro de 100 a 600.000;
- `max_rows`: inteiro de 1 a 1.000.000.

Não aceitar booleanos, decimais ou coerções silenciosas.

**SQL policy:** apenas inclusão em `denied_functions`, por `PUT /sql`.

- Sem remover ou renomear negações.
- Deduplicação e normalização são confirmadas pela releitura do servidor.
- Não reimplementar `casefold` do Python como autoridade no navegador.
- `allowed_pg_functions` e proteções efetivas são somente leitura.
- Nenhuma mutação inclui `allowed_pg_functions`, nem como `null` ou lista vazia.

### 3.9. Validação

`POST /config:validate` é explícito, sem chamadas a cada tecla.

- Enviar documento candidato na raiz, não o envelope GET.
- Nunca enviar `expected_revision`.
- Construir o candidato a partir do snapshot-base e do rascunho.
- Preservar os valores protegidos atuais na cópia de validação.
- Invalidar o resultado ao mudar rascunho ou base.

Para candidato que cria itens sem IDs, usar projeção transitória sem IDs e sem revision, aceita como documento não adotado. Essa projeção não é persistida e não modifica a identidade do snapshot.

Identificar seu limite: valida conteúdo e compilação; não valida identidade administrativa nem reserva revision.

Sucesso é exatamente:

- `valid=true`;
- `schema_validated=true`;
- `policy_compiled=true`;
- `database_checks_performed=false`.

Não significa salvo, conexão testada ou segurança de mascaramento comprovada para todos os dados.

### 3.10. Adoção legada

Com `adopted=false`, permitir leitura e validação; bloquear edição.

A confirmação deve explicar:

- atribuição de IDs e publicação de revision 1;
- perda possível de comentários e formatação do principal;
- backup dos bytes originais pelo backend;
- ausência de mudança intencional na política de masking.

Checkbox inicialmente desmarcado e ação final “Adotar configuração”. Apenas esse gesto envia `expected_revision=0` e `confirm_comment_loss=true`, booleano literal.

Não adotar automaticamente. Não mostrar caminhos ou conteúdo de backup, ausentes da resposta.

### 3.11. Revision e concorrência

Atualização otimista significa controle por revision, não sucesso antecipado.

Cada edição conserva snapshot-base, revision-base, rascunho e resultado pendente.

Regras:

1. Toda revision recebida deve satisfazer `Number.isSafeInteger` e ser não negativa **antes de entrar no estado**.
2. Validar revisions em GET, respostas de escrita, conflitos e durabilidade.
3. Revisions inconsistentes no mesmo envelope invalidam a resposta.
4. Não arredondar, converter string ou usar valor inválido.
5. Bloquear nova escrita se a próxima revision não puder ser representada com segurança.
6. Capturar `expected_revision` junto do conteúdo editado.
7. Polling não troca a revision-base do rascunho.
8. Permitir uma escrita pendente por aba, sem fila ou retry automático.
9. Sucesso requer resposta válida com `applied=true`; reler configuração em seguida.
10. Novos IDs vêm da releitura, não de inferência por nome.
11. Respostas antigas ou de sessão encerrada não atualizam o estado.
12. Abas não compartilham token ou rascunho; o servidor arbitra concorrência.

### 3.12. Estados e recuperação

| Resultado | Comportamento |
|---|---|
| Loading | Não apresentar configuração vazia como real |
| Lista vazia confirmada | Explicar ausência e oferecer criação quando permitida |
| Rascunho alterado | Indicar não salvo; permitir cancelar |
| Escrita pendente | Bloquear novas mutações |
| `401` | Limpar token, configuração e rascunhos; voltar à entrada |
| Host/origem recusados | Mensagem fixa; não sugerir desabilitar proteção |
| Item `404` | Relê lista e revisa rascunho |
| `REVISION_CONFLICT` | Preserva rascunho; carrega base nova separadamente; exige revisão |
| `CONFIG_NOT_ADOPTED` | Bloqueia edição e oferece adoção |
| `CONFIG_ALREADY_ADOPTED` | Relê; não repete adoção |
| `CONFIG_OUT_OF_SYNC` | Bloqueia escritas; recuperação operacional fora da UI |
| `RELOAD_BUSY` | Mantém rascunho; oferece atualização e nova tentativa manual |
| `413` | Informa limite; não divide operação atômica |
| `415` ou `IMMUTABLE_FIELD` | Incompatibilidade/defeito do cliente; sem correção silenciosa |
| `SCHEMA_INVALID` | Motivos sanitizados associados somente a campos conhecidos |
| `CONFIG_INVALID` | Candidato inválido; sem inventar causa |
| `CONFIG_RELOAD_ERROR` | Falha ao compilar/verificar candidato; não diagnostica automaticamente PostgreSQL |
| `CONFIG_WRITE_ERROR` | Falha de persistência; mantém rascunho |
| `CONFIG_DURABILITY_ERROR` | **Aplicada; durabilidade não confirmada**; relê, sem repetição cega |
| Timeout, desconexão, resposta inválida ou `INTERNAL_ERROR` durante escrita | **Resultado desconhecido**; reconciliar antes de nova mutação |

`RELOAD_BUSY` não possui prazo máximo garantido. Não estimar liberação pelo timeout SQL.

Cancelar fetch ou perder resposta não garante cancelamento da operação no servidor. Revision maior não prova autoria desta aba. Se a ambiguidade persistir, bloquear escritas e exigir verificação operacional.

Se a escrita confirmou sucesso e apenas a releitura falhou, mostrar “Salva; visualização ainda não atualizada”.

“Parcialmente aplicado” não significa metade das regras publicada: o runtime é um agregado. As situações relevantes são durabilidade não confirmada, resposta perdida ou falha excepcional entre persistência e publicação. Nenhuma autoriza rollback automático.

### 3.13. Indisponibilidade e acessibilidade

- API indisponível antes de abrir: a UI não carrega.
- API cai com aba aberta: última leitura fica desatualizada, polling suspende e mutações bloqueiam.
- PostgreSQL indisponível no startup: preservar falha de inicialização.
- PostgreSQL cai depois: leituras administrativas e validação sem conexão podem funcionar; escrita pode falhar na verificação do candidato.
- Sem botão “Testar conexão”, health check SQL ou endpoint diagnóstico adicional.

A interface deve oferecer HTML semântico, labels, foco visível, navegação por teclado, diálogos acessíveis, anúncios de estados, contraste e reorder de regras sem mouse.

Deve funcionar a 320 CSS pixels e com zoom de 200%, respeitar redução de movimento e não usar apenas cor para comunicar resultado.

### 3.14. Fronteira público/privado

O bootstrap será **um interpretador declarativo de vocabulário fechado**. Ele é genérico apenas dentro do protocolo de apresentação descrito abaixo. Esse custo é assumido explicitamente.

Não é permitido reconstruir schemas privados no JavaScript por concatenação, codificação, minificação ou dados embutidos.

**Vocabulário público permitido**

| Categoria | Exposição permitida |
|---|---|
| Rotas | Os quatro caminhos UI de §5.1 e o prefixo de segurança `/admin/v1/`; nenhum caminho administrativo completo |
| Transporte | `Authorization`, `Bearer`, `Content-Type`, `application/json`, opções Fetch e métodos `GET`, `HEAD`, `POST`, `PUT`, `DELETE` |
| Apresentação | Chaves e discriminantes do protocolo declarativo abaixo |
| Operações abstratas | Ler, criar, substituir, excluir, mover, validar, confirmar e acrescentar conjunto |
| Estados abstratos | Loading, autenticação, rascunho, pendente, sucesso, conflito, ocupado, incompatível, desconhecido e durabilidade incerta |
| Nomes compartilhados | `id`, `name`, `value`, `type`, `mode`, `length`, `path`, `fields`, `error`, `detail`, quando usados no protocolo genérico ou APIs do navegador |
| Segurança | Literais recusados, inclusive `__proto__`, `constructor` e `prototype` |
| Integridade | Versão do protocolo e SHA-256 do recurso estático privado |

Nenhum nome de transformer aparece nos assets públicos.

Nenhuma categoria administrativa de erro em formato de wire aparece nos assets públicos. Antes dos metadados, o bootstrap trata apenas status HTTP com mensagens genéricas.

As respostas HTTP públicas de erro continuam usando categorias de fronteira existentes; essa exposição já pertence ao contrato HTTP e não é exposição do schema administrativo.

**Vocabulário privado**

- todos os caminhos completos sob `/admin/v1`;
- nomes e estruturas dos DTOs administrativos;
- nomes dos oito transformers;
- parâmetros, defaults e restrições desses transformers;
- todas as categorias administrativas e reason codes de validação;
- nomes de operações de negócio/auditoria;
- campos dos schemas HTTP, exceto os nomes compartilhados listados acima;
- formatos/prefixos de IDs e valores das proteções.

Inclui, entre outros: `revision`, `expected_revision`, `current_revision`, `adopted`, `applied`, `masking`, `rules`, `rule`, `exceptions`, `exception`, `database`, `sql`, `config`, `match`, `case_sensitive`, `transformer`, `position`, `rule_ids`, `statement_timeout_ms`, `max_rows`, `allowed_pg_functions`, `denied_functions`, `confirm_comment_loss`, `runtime`, `counters`, `secrets`, `pattern`, `replacement`, `strategy` e `preserve_length`.

A lista normativa será calculada a partir dos schemas, rotas, registry e enums atuais, subtraindo apenas a lista pública explícita. Não poderá ser reduzida para fazer um teste passar.

**Exposição residual aceita:** um visitante pode reconhecer um cliente administrativo declarativo, seu mecanismo de bearer, operações abstratas e controles de concorrência. Pode conhecer os nomes compartilhados, a entrada privada e sondar os erros de fronteira. Não se promete ocultar a existência do produto, o código do repositório ou informação obtida de outras fontes.

### 3.15. Conteúdo de `presentation.json`

Documento estático UTF-8, sem dados de instalação ou runtime. Raiz com **exatamente**:

| Chave | Conteúdo |
|---|---|
| `format` | Inteiro literal `1` |
| `models` | Modelos fechados de request/response das chamadas consumidas |
| `calls` | Catálogo exato de oito GETs, uma validação e dez escritas utilizadas pela UI |
| `views` | Seis telas autenticadas de §3.2, campos, labels e referências |
| `editors` | Definições dos oito transformers de §3.7 |
| `bindings` | Ligações entre propriedades wire e papéis internos, como versão, identidade, ordem, adoção e resultado |
| `messages` | Textos fixos em português e mapeamentos de erros/reasons para estados abstratos |

IDs internos são opacos, locais ao documento, únicos e não são IDs administrativos.

Conteúdo permitido:

- modelos de objeto fechado, lista, string, booleano, inteiro seguro, enum, nullable e união discriminada;
- propriedades obrigatórias/opcionais, limites e referências internas;
- defaults de formulário explicitamente definidos nesta especificação;
- controles de texto, inteiro, checkbox, seleção, tabela/lista, leitura e confirmação;
- caminhos de campo como vetores de segmentos, nunca expressões;
- projeções limitadas a selecionar/copiar campos, construir objetos/listas, omitir metadata, inserir/substituir/remover um item e aplicar uma permutação;
- condições limitadas a presença, igualdade com literal, escolha de união e dependência booleana de controles;
- mensagens fixas, sem HTML ou templates executáveis.

Não contém:

- estado atual, revision atual, IDs reais, configuração, contadores ou secrets;
- caminhos de filesystem, DSN ou valores ambientais;
- exemplos de dados do banco;
- JavaScript, regex executável pelo navegador, HTML, CSS ou URLs externas;
- referências remotas, importações, callbacks, loops programáveis ou funções;
- configuração de auditoria.

O catálogo contém dez escritas porque **`PUT /config` não é consumido pela UI**. A API continua com onze, e seus onze contratos continuam cobertos pela tipagem e regressão; o contrato de substituição completa não é uma operação autorizada do cliente UI.

### 3.16. Limites do interpretador

- No máximo seis views, oito editores e dezenove chamadas.
- No máximo 128 modelos, profundidade declarativa 16 e 512 controles.
- Referências internas precisam existir; ciclos são recusados.
- Objetos têm chaves fechadas; metadado desconhecido invalida o documento inteiro.
- Métodos são somente os declarados no catálogo aprovado.
- Destinos são relativos à raiz, sob `/admin/v1/`, sem query, fragmento, esquema, autoridade, `%`, barra invertida ou segmentos `.`/`..`.
- Templates permitem somente um segmento de identidade validado, sem interpolação livre.
- Token não é fonte disponível para projeções de corpo.
- `__proto__`, `constructor` e `prototype` são recusados como chaves/segmentos estruturais em qualquer nível.
- Não usar merge genérico em objetos do navegador.
- Uma string administrativa com esses textos continua sendo dado textual; a proibição estrutural não reinterpreta valores legítimos.

O servidor valida o documento contra o catálogo privado exato aprovado antes do bind.

O bootstrap carrega um hash fixo do `presentation.json` correspondente à sua versão. Confere os bytes antes de interpretá-los e faz validação estrutural adicional. Hash divergente, metadado desconhecido, método ou destino inválido bloqueiam a sessão, sem requests de negócio.

Essa âncora evita depender de uma allowlist administrativa duplicada no JavaScript público. Não é assinatura nem proteção contra comprometimento integral do pacote.

Antes de receber e validar os metadados autenticados, o bootstrap só pode fazer fetch de **`/admin/ui/presentation.json`**, após entrada explícita do token. Não chama `/status`, `/config` ou qualquer outra API para descobrir capacidades.

## 4. Contrato de segurança do navegador

### 4.1. Token e memória

Token exclusivamente em `Authorization: Bearer`.

Nunca em URL, cookie, HTML servido, atributos HTML, bundle, logs, console, mensagens de erro, `localStorage`, `sessionStorage`, IndexedDB, Cache Storage ou arquivos.

Entrada password, sem valor inicial, sem correção ortográfica e sem preenchimento automático solicitado. O valor existe transitoriamente na propriedade do controle e é limpo após a tentativa.

Após autenticação, manter referência privada no transporte, não no estado de apresentação ou objeto global.

Limpeza obrigatória:

- sair ou receber `401`: remover token, metadados privados, configuração e rascunhos;
- `pagehide`: limpar as mesmas referências, limpar o DOM administrativo, cancelar leituras e invalidar a geração da sessão;
- `pageshow`: começar sem sessão, inclusive quando `event.persisted=true`;
- callbacks tardios de geração anterior não podem restaurar conteúdo ou token;
- reload e BFCache exigem nova entrada.

Cancelar requests durante a limpeza não significa desfazer escrita já admitida no servidor.

Sem service worker, armazenamento offline, compartilhamento por `postMessage`, BroadcastChannel ou sincronização entre abas.

### 4.2. Origem exata, somente com UI ligada

Validar Host antes de autenticação:

- somente `127.0.0.1`, `localhost` e `[::1]`;
- porta efetiva do listener;
- nenhuma resolução DNS para decidir confiança;
- recusar duplicatas, listas, userinfo, sufixos, ponto final, zonas IPv6 e autoridades ambíguas.

A referência é a tupla **`(http, host validado, porta efetiva)`**.

Se existir `Origin`, exigir uma única origem válida, não opaca e exatamente igual. Se existir `Referer`, exigir URL absoluta válida cuja origem seja exatamente igual. Se ambos existirem, ambos precisam passar.

- `null`, vazio e origem externa: `403`.
- Hosts loopback diferentes não são equivalentes.
- Porta diferente não é equivalente.
- HTTPS não é equivalente a HTTP.
- Porta omitida equivale a 80 somente quando o listener HTTP está efetivamente em 80.
- Ausência de ambos continua permitida a clientes HTTP nativos autenticados.

Normalização limitada à autoridade válida, caixa de hostname e porta efetiva; não fazer equivalência por endereço resolvido.

`Sec-Fetch-Site` presente com `cross-site`, `same-site` ou valor inválido é recusado. Ausência ou `none` não concede autenticação.

Não usar `Forwarded` ou `X-Forwarded-*` como autoridade. Com UI ligada, configurar `proxy_headers=False`. O default do Uvicorn pode confiar em encaminhamento vindo de loopback. [Uvicorn](https://uvicorn.dev/settings/)

### 4.3. Fetch normativo

**Todo fetch da UI**, inclusive `presentation.json`, deve usar:

| Item | Valor/regra |
|---|---|
| URL | Relativa validada, sem query ou fragmento |
| `mode` | `"cors"` |
| `credentials` | `"omit"` |
| `redirect` | `"error"` |
| `cache` | `"no-store"` |
| `referrerPolicy` | `"no-referrer"` |
| Authorization | Anexado somente após confirmar `url.origin === window.location.origin` |

Após resolver a URL, validar novamente caminho e método contra a operação autorizada. Não aceitar URL fornecida por formulário ou resposta de erro.

Métodos com corpo enviam `Content-Type: application/json`, inclusive DELETE. Nenhum request envia token no corpo.

`mode: "cors"` não habilita CORS no servidor. Em métodos diferentes de GET/HEAD, `no-referrer` combinado com modo não-CORS pode serializar Origin como `null`. A combinação definida acima deve ser confirmada em Chromium, Firefox e WebKit. [Padrão Fetch](https://fetch.spec.whatwg.org/)

Não adicionar rota `OPTIONS` ou qualquer header `Access-Control-*`.

O carregamento declarativo de HTML, JS e CSS pelo navegador não é um fetch programado pela aplicação e não recebe Authorization.

### 4.4. XSS, recursos e erros

Todos os valores administrativos são texto não confiável.

- Usar nós de texto, `textContent` e propriedades de controles.
- Proibir `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` e `Function`.
- Sem Markdown/HTML em mensagens.
- Sem valores administrativos em URLs, CSS, handlers ou seletores.
- Não mostrar corpo bruto de resposta inesperada.
- Erros usam categoria fechada e mensagem local; caminhos desconhecidos não são interpolados.
- Sem scripts, fontes, imagens, analytics ou assets externos.
- Sem previews de regex ou transformação.

Não gravar trace, HAR, vídeo ou screenshot contendo token **ou dados administrativos**, inclusive nos testes. Capturas desses conteúdos em memória para asserção não podem ser serializadas por reporters ou diagnósticos de falha.

DevTools, extensões privilegiadas e sistema operacional comprometido permanecem fora das garantias de sigilo da aplicação.

### 4.5. Threat model

| Ameaça | Controle |
|---|---|
| Site externo ou processo em outra porta | Origem exata, bearer explícito e ausência de CORS |
| DNS rebinding | Host literal, sem confiança em resolução DNS |
| CSRF por formulário/fetch | Sem credenciais ambientes, origem recusada e nenhum GET mutável |
| XSS armazenado | Texto, controles fechados, CSP e ausência de execução dinâmica |
| Clickjacking | CSP de framing e `X-Frame-Options` |
| Vazamento em cache/histórico/BFCache | Memória, `no-store`, limpeza explícita e nenhuma persistência |
| Encaminhamento do bearer | Origem conferida antes do header e redirects recusados |
| Metadados de apresentação adulterados | Hash fixo, gramática fechada e catálogo aprovado |
| Concorrência/perda de resposta | Revision, estado desconhecido e ausência de retry cego |
| Assets/pacote comprometidos | Integridade e build verificável; comprometimento integral do pacote continua fora dessa garantia |
| DoS local | Recursos pequenos e fixos; não se promete eliminar DoS local |

Secrets continuam somente `configured` ou `missing`. Nenhuma informação de estado ou schema administrativo é retornada por falha de autenticação.

## 5. Rotas, respostas e impacto na Fase 7

### 5.1. Inventários exatos

**Inventário A — UI desligada**

Oito rotas GET/HEAD:

- `/admin/v1/status`
- `/admin/v1/config`
- `/admin/v1/rules`
- `/admin/v1/rules/{rule_id}`
- `/admin/v1/exceptions`
- `/admin/v1/exceptions/{exception_id}`
- `/admin/v1/transformers`
- `/admin/v1/protected`

Uma validação:

- `POST /admin/v1/config:validate`

Onze escritas:

- `POST /admin/v1/config:adopt`
- `PUT /admin/v1/config`
- `POST /admin/v1/rules:reorder`
- `POST /admin/v1/rules`
- `PUT /admin/v1/rules/{rule_id}`
- `DELETE /admin/v1/rules/{rule_id}`
- `POST /admin/v1/exceptions`
- `PUT /admin/v1/exceptions/{exception_id}`
- `DELETE /admin/v1/exceptions/{exception_id}`
- `PUT /admin/v1/database`
- `PUT /admin/v1/sql`

Total: vinte entradas declaradas e 28 pares método/caminho.

**Inventário B — UI ligada**

Inventário A, acrescido de:

| Métodos | Caminho | Acesso |
|---|---|---|
| GET, HEAD | `/admin/ui` | Público |
| GET, HEAD | `/admin/ui/assets/ui.js` | Público |
| GET, HEAD | `/admin/ui/assets/ui.css` | Público |
| GET, HEAD | `/admin/ui/presentation.json` | Bearer |

Total: 24 entradas declaradas e 36 pares método/caminho.

Nenhuma outra rota. Sem montagem genérica, fallback SPA, directory listing, sourcemap, redirecionamento de slash ou arquivo servido pelo caminho recebido.

### 5.2. Precedência das recusas

Com UI ligada, para requisições HTTP aceitas pelo parser do servidor:

1. Fronteira externa contém exceções e aplica headers.
2. Host inválido → `400 HOST_NOT_ALLOWED`.
3. Origin/Referer/Fetch Metadata recusado → `403 CROSS_ORIGIN_REJECTED`.
4. Content-Length declarado acima de 1 MiB → `413 PAYLOAD_TOO_LARGE`.
5. Autenticação, exceto GET/HEAD dos três caminhos públicos **raw e canônicos**.
6. Content-Type dos métodos com corpo → `415` se não for JSON.
7. Roteamento UI exato: caminho, query string e método.
8. Handler do recurso.

O limite streaming continua autoritativo quando o corpo é consumido, como na Fase 7. Não prometer um `413` antecipado para um corpo ainda não lido.

A exceção pública não usa prefixos. Query string não participa da identificação do caminho público, mas é recusada antes da entrega do recurso.

As únicas recusas anteriores à autenticação são as de fronteira acima. Uma variante não canônica não ganha acesso público.

Requests que o parser HTTP recusar antes do ASGI pertencem ao contrato do servidor, não aos handlers UI. Os testes devem distinguir esse caso, sem afirmar headers da aplicação onde ela não executou.

### 5.3. Matriz de respostas

Nas linhas abaixo, pressupõem-se Host/origem/tamanho válidos. POST/PUT/PATCH/DELETE autenticados sem JSON recebem `415` antes do roteamento, conforme a precedência.

| Situação | Sem token ou token incorreto | Token válido |
|---|---|---|
| Admin API desligada, UI desligada | Nenhum listener | Nenhum listener |
| UI desligada: GET/HEAD de qualquer caminho UI | `401` | `404` |
| UI desligada: outros métodos em caminho UI | Comportamento original: `401` | `415` se aplicável; caso contrário `404` |
| UI ligada: GET/HEAD público canônico, sem query | `200`; token ignorado para esse recurso público | `200` |
| UI ligada: GET/HEAD de `presentation.json`, sem query | `401` | `200` |
| Query string não vazia em recurso público canônico GET/HEAD | `404` | `404` |
| Query string não vazia em `presentation.json` | `401` | `404` |
| Trailing slash | `401` | `404` |
| Caminho semelhante, mas não idêntico | `401` | `404` |
| Caminho percent-encoded que tentaria alcançar recurso UI | `401` | `404` |
| Traversal, barras invertidas ou outra forma não canônica para UI | `401` | `404` |
| Asset não pertencente ao inventário | `401` | `404` |
| Método não registrado em recurso UI canônico, sem query | `401` | `405`, após verificações anteriores |
| `OPTIONS` externo com origem recusada | `403` | `403` |
| `OPTIONS` sem origem recusada, em caminho UI canônico | `401` | `405` |
| Falha interna ao servir bytes já validados | Recursos públicos: `500`; privado: `401` | `500` |

Um delimitador `?` sem conteúdo, indistinguível de query vazia na interface ASGI atual, é tratado como query vazia. A proibição refere-se a `query_string` não vazia; não se alegará detectar informação que o servidor descartou.

A conferência dos caminhos UI usa `raw_path`, sem decodificar, normalizar ou redirecionar para conceder a exceção pública. A disponibilidade de `raw_path` é requisito do servidor suportado.

Um navegador pode normalizar traversal antes de enviar. Nesse caso, o servidor aplica o contrato ao caminho efetivamente recebido. Essa normalização nunca autoriza a exceção pública para uma rota administrativa.

Nenhuma das quatro rotas UI, seus erros ou recusas gera `AdminAudit`, incrementa contador administrativo, valida configuração ou acessa PostgreSQL.

### 5.4. Corpo e headers das respostas

Sucesso GET:

- `/admin/ui`: bytes exatos do HTML validado;
- `ui.js`: bytes exatos do ESM validado;
- `ui.css`: bytes exatos do CSS validado;
- `presentation.json`: bytes exatos do JSON privado validado.

Sem interpolação de token, Host, parâmetros ou estado nesses bytes.

Erros usam o serializador canônico existente, com `error` e `detail` fixos, sem `fields`, revision ou `applied` para recursos UI:

| Status | Categoria | Detail |
|---|---|---|
| 400 | `HOST_NOT_ALLOWED` | `The Host header is not accepted.` |
| 401 | `UNAUTHORIZED` | `Authentication is required.` |
| 403, UI ligada | `CROSS_ORIGIN_REJECTED` | `The request origin is not accepted.` |
| 404 | `NOT_FOUND` | `The requested resource does not exist.` |
| 405 | `METHOD_NOT_ALLOWED` | `The method is not allowed for this resource.` |
| 413 | `PAYLOAD_TOO_LARGE` | `The request body is too large.` |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | `The request body must be application/json.` |
| 500 | `INTERNAL_ERROR` | `The administrative operation could not be completed.` |

Com UI desligada, inclusive o detail anterior de origem permanece inalterado.

HEAD repete autenticação, validações, status e headers de representação do GET correspondente, com corpo vazio. `Content-Length` representa o tamanho do corpo que o GET enviaria, inclusive em erro.

Com UI ligada, aplicar:

| Header | Valor |
|---|---|
| `Cache-Control` | `no-store` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `no-referrer` |
| `X-Frame-Options` | `DENY` |
| `Cross-Origin-Resource-Policy` | `same-origin` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), fullscreen=()` |

MIME exato dos recursos:

- HTML: `text/html; charset=utf-8`;
- JS: `text/javascript; charset=utf-8`;
- CSS: `text/css; charset=utf-8`;
- JSON: `application/json`.

Não emitir `Access-Control-*`, `Set-Cookie`, `Server`, ETag ou Last-Modified. Não usar 304, Range/206 ou compressão nesta fase; ignorar condicionais/Range e retornar a representação completa autorizada. Para os novos `405`, não acrescentar header `Allow`, preservando a política do serializador atual.

CSP dos recursos UI bem-sucedidos:

```text
default-src 'none'; script-src 'self'; script-src-attr 'none'; style-src 'self'; style-src-attr 'none'; connect-src 'self'; img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'; frame-ancestors 'none'; worker-src 'none'; manifest-src 'none'; media-src 'none'
```

JSON administrativo e erros, com UI ligada:

```text
default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

Sem `unsafe-inline`, `unsafe-eval`, `data:`, `blob:` ou relatórios CSP enviados a endpoints. CSP é header HTTP, não apenas meta. [CSP — W3C](https://www.w3.org/TR/CSP/)

### 5.5. Assets e manifesto antes do bind

Limites inclusivos dos bytes UTF-8:

| Recurso | Máximo |
|---|---:|
| HTML | 16 KiB |
| JavaScript público | 512 KiB |
| CSS | 64 KiB |
| `presentation.json` | 256 KiB |
| Manifesto interno | 16 KiB |

Sem assets adicionais, fontes ou imagens. Tamanho declarado e real devem coincidir; leitura é limitada a máximo + 1 byte.

Manifesto interno, não servido por HTTP:

- versão de formato;
- exatamente quatro entradas;
- identificador fixo do recurso;
- caminho relativo fixo dentro do pacote;
- MIME;
- tamanho;
- SHA-256 dos bytes.

Recusar entradas extras, ausentes ou duplicadas, campos desconhecidos, caminhos fora da lista, hashes inválidos, tamanhos excedidos, JSON duplicado/malformado e referências inconsistentes.

O hash do manifesto será fixado no pacote durante o build; o JavaScript fixa o hash do JSON privado. O build calcula primeiro o JSON, depois o JS e por último o manifesto, evitando dependência circular.

Validar bytes, hashes, UTF-8, gramática de apresentação, catálogo de chamadas e compatibilidade antes do bind. Ler somente recursos embarcados, nunca cwd ou caminho configurável.

Recurso ausente/corrompido, manifesto inválido ou incompatibilidade:

- falha de startup antes da porta e MCP;
- stderr exatamente `maskgw: falha na inicializacao\n`;
- exit code `1`;
- nenhuma resposta HTTP parcial, fallback ou modo degradado.

Após startup, servir os bytes imutáveis já verificados. Alteração do pacote em disco não muda esses bytes em execução; será detectada no próximo startup.

### 5.6. Alterações delimitadas na Fase 7

Somente com UI ligada:

- quatro novas rotas;
- três exceções públicas exatas;
- comparação exata de mesma origem;
- parsing estrito de Host/origens;
- proxy headers desligados;
- headers de navegador;
- detail de origem compatível com a nova política.

Nenhuma alteração nos schemas de negócio, seção crítica, persistência, auditoria, runtime ou MCP.

A matriz da Etapa 11 deverá verificar os dois inventários por igualdade exata. Não substituir fechamento por testes do tipo “contém pelo menos estas rotas”.

## 6. Build, tipagem e plano de testes

### 6.1. Stack e versões

Escolha: **JavaScript ESM com JSDoc, TypeScript `checkJs`, strict e `noEmit`**.

Justificativa: mantém ESM diretamente executável, sem compilação de runtime ou bundler, usando o sistema de tipos do TypeScript para estados, DTOs e transporte.

Fixar:

- Node.js `24.20.0`;
- npm `11.19.0`;
- `@playwright/test` `1.63.0`;
- `typescript` `5.9.3`.

TypeScript 5.9.3 é uma versão estável publicada; `checkJs` aplica verificação aos arquivos JavaScript. [TypeScript 5.9.3](https://github.com/microsoft/TypeScript/releases/tag/v5.9.3), [checkJs](https://www.typescriptlang.org/tsconfig/checkJs.html)

Configuração obrigatória: `allowJs`, `checkJs`, `strict`, `noEmit`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` e `skipLibCheck=false`.

Tipos administrativos completos podem ficar em declarações privadas não servidas. Anotações presentes no asset público só podem referenciar tipos abstratos e respeitar a lista de vocabulário público.

Exigir:

- entrada externa tratada como `unknown`;
- narrowing e validadores antes de uso;
- uniões discriminadas para estados e desfechos;
- checagem dos onze contratos existentes da API;
- conjunto tipado de dez escritas autorizadas para a UI;
- nenhuma passagem de `any`, `@ts-ignore`, `@ts-nocheck` ou cast para contornar contrato;
- fixtures negativas de tipagem para provar rejeição de combinações inválidas.

Se a implementação não conseguir expressar esses contratos sem anular a checagem, a etapa fica bloqueada para revisão da escolha; não enfraquecer o gate silenciosamente.

Usar lockfile npm v3, dependências diretas exatas e transitivas fixadas com integridade. Instalação congelada por `npm ci`. Nenhuma atualização incidental das dependências Python.

### 6.2. Build e distribuição

Nenhuma biblioteca de runtime no navegador, bundler, CDN, servidor Node ou download em startup.

Build determinístico:

1. verificar tipagem;
2. validar o documento de apresentação;
3. calcular seu hash;
4. montar o único ESM público com essa constante;
5. validar vocabulário e limites dos bytes finais;
6. gerar manifesto e sua âncora;
7. incluir os quatro recursos no wheel/sdist.

Nenhuma variável ambiental, segredo, sourcemap, tipo privado, fixture ou arquivo de teste é servido.

O usuário final precisa somente do pacote Python e navegador. O pacote instalado deve funcionar sem checkout e sem Node/npm.

### 6.3. Testes unitários e de contrato

- resolução bruta da flag, incluindo espaços;
- dependência UI/Admin e ordem de startup;
- manifesto, hashes, tamanhos e corrupção;
- parsers de Host/origem e matriz de recusas;
- tipagem de estados, revisões e requests;
- serializers granulares e ausência de campos protegidos;
- exclusão de `PUT /config` do transporte UI;
- projeção de validação sem metadata;
- semântica dos formulários de transformers;
- respostas tardias, geração de sessão e limpeza;
- revisions inseguras recusadas antes do estado;
- reorder de regras como permutação completa;
- CRUD de exceptions sem reorder ou substituição integral.

### 6.4. Testes dos bytes públicos

Examinar os bytes finais de HTML, JS e CSS, tanto no build quanto nas respostas HTTP do pacote instalado.

Provar ausência de:

- caminhos administrativos completos;
- campos privados calculados dos schemas;
- nomes de transformers;
- categorias/reason codes privados;
- nomes privados das operações;
- formatos de IDs;
- dados e secrets marcadores.

Examinar também literais JavaScript decodificados para impedir vazamento por escapes. É proibido dividir, codificar ou reconstruir vocabulário privado para contornar a busca.

Adicionar contraprovas que injetem marcadores privados em cada recurso e demonstrem a falha do verificador.

Esse teste prova a ausência do vocabulário declarado nos bytes/literais examinados; não é apresentado como prova de confidencialidade contra inferência ou informação externa.

### 6.5. Testes de componentes

Usar **runner padrão do Playwright sobre páginas-fixture locais**, com componentes reais e transporte controlado.

Não usar pacotes experimentais de Component Testing.

Cobrir:

- entrada e limpeza de sessão;
- loading, vazio, falha e retry;
- CRUD, confirmações e navegação com rascunho;
- reorder de regras por teclado;
- conflito, busy, durabilidade e resultado desconhecido;
- foco, acessibilidade, zoom, viewport e textos longos;
- XSS e metadados inválidos.

Fixtures não entram no pacote nem no inventário de produção.

### 6.6. End-to-end real

Servidor HTTP, `AdminConfigService`, arquivos temporários e PostgreSQL de testes reais.

Matriz Playwright 1.63.0:

- Chromium 153.0.8010.12;
- Firefox 155.0;
- WebKit 26.6.

Registrar também as revisões dos binários usadas. [Release oficial](https://github.com/microsoft/playwright/releases/tag/v1.63.0)

Fluxos:

- autenticação e leitura;
- adoção explícita e backup;
- CRUD de regras e exceptions;
- reorder somente de regras;
- database e SQL aditivo;
- validação;
- persistência e restart;
- indisponibilidade da API/PostgreSQL;
- pacote instalado sem checkout;
- shutdown e coexistência MCP;
- duas abas e conflitos;
- runtime aposentado em uso.

A UI nunca executa SQL. O harness pode usar o MCP existente para comprovar que a configuração aplicada afeta o masking, sem criar controles ou endpoints de consulta.

### 6.7. Testes adversariais obrigatórios

**Origem/CSRF**

- origem externa, porta local diferente e aliases loopback;
- métodos de escrita reais com as opções Fetch normativas;
- formulário, JSON, Authorization e preflight;
- origem opaca/sandbox;
- Origin legítimo com Referer externo e o inverso;
- Host duplicado, DNS rebinding e forwarding falsificado;
- confirmação positiva em três engines, sem `Origin: null`.

**Bootstrap e metadados**

- antes de autenticar, nenhuma chamada administrativa;
- antes de validar metadados, somente fetch de `presentation.json`;
- nenhuma chamada após metadado desconhecido, hash inválido ou referência cíclica;
- URLs absolutas, relativas fora do contrato, métodos inesperados e templates hostis recusados;
- `__proto__`, `constructor` e `prototype` recusados estruturalmente.

**XSS**

Persistir valores hostis em `match`, parâmetros e strings administrativas; abrir outra sessão e provar texto preservado, ausência de execução e ausência de rede externa.

Testar HTML, handlers, `</script>`, URLs executáveis e mensagens inesperadas. Detectores de execução/rede precisam de controles positivos no harness.

**Leakage e lifecycle**

- token marcador somente no Authorization autorizado;
- nenhum store, URL, HTML, log, erro ou console;
- `pagehide`/`pageshow`, BFCache, reload, sair e `401`;
- respostas tardias não restauram dados;
- redirects não encaminham bearer;
- sem trace, HAR, vídeo ou screenshot contendo token ou dados administrativos;
- reporters emitem somente resultados sanitizados.

**HTTP e assets**

Executar todas as combinações de §5.3, inclusive HEAD, query, método, percent-encoding, traversal e caminhos semelhantes.

Corromper/remover cada recurso e manifesto; provar que não houve bind, conexão PostgreSQL ou disponibilização MCP quando a validação prévia falhou.

**Concorrência e persistência**

- duplo clique, abas concorrentes e respostas fora de ordem;
- mudança entre leitura, validação e escrita;
- edição externa;
- busy;
- falha pré-replace;
- durabilidade pós-replace;
- resposta perdida após publicação;
- sucesso seguido de falha de releitura.

Verificar arquivo, digest, runtime, IDs e auditoria conforme o desfecho. Nenhum endpoint de fault injection no produto.

### 6.8. Gate

Ao final de cada etapa:

- tipagem frontend sem erros;
- testes Node e Playwright acumulados verdes;
- suíte Python e verificações existentes verdes;
- integração real sem skips por ausência de DSN;
- browsers requeridos disponíveis;
- nenhum finding convertido em `skip`/`xfail`.

A baseline documental da Fase 7 registra 2.312 coletados, 2.304 aprovados e 8 skips de plataforma no Windows. É evidência histórica, não execução desta revisão.

## 7. Implementação incremental, aceite e rollback

### 7.1. Etapas

| Etapa | Entrega | Gate específico |
|---|---|---|
| 1 | Especificação aprovada, decisões e matriz de rastreabilidade | Baseline reproduzida |
| 2 | Tipos, gramática declarativa, catálogo privado e build | Tipagem, bytes públicos, limites e manifesto verdes |
| 3 | Flag bruta e validação pré-bind | Compatibilidade com UI desligada e falhas sem recursos abertos |
| 4 | Rotas, autenticação, origem e headers | Matriz HTTP completa e fetch real nos três browsers |
| 5 | Sessão, lifecycle e telas somente leitura | Leakage, BFCache e acessibilidade |
| 6 | Máquina de estados e transporte granular | Revision, conflito, busy, durabilidade e resultado desconhecido |
| 7 | Adoção, validação e CRUD | Sem efeitos indevidos e confirmação explícita |
| 8 | Reorder de regras, database e SQL aditivo | Preservação de exceptions e campos protegidos |
| 9 | Pacote instalado e revisão adversarial final | Todas as suítes e critérios de aceite |

Cada etapa termina com suíte verde. Não avançar funcionalidade administrativa sobre uma fronteira ainda reprovada.

### 7.2. Aceite

A fase estará concluída somente quando:

- os inventários forem exatos;
- UI desligada preservar a superfície anterior;
- UI ligada funcionar sem CORS e bloquear origens externas;
- bootstrap e apresentação respeitarem a divisão público/privado;
- token e dados administrativos não forem persistidos;
- todos os fluxos e desfechos estiverem cobertos;
- não houver reorder de exceptions ou `PUT /config` originado pela UI;
- campos protegidos permanecerem imutáveis;
- pós-commit não for apresentado como rollback;
- pacote instalado funcionar sem ferramentas frontend;
- acessibilidade, lifecycle, auditoria existente e stdout MCP permanecerem corretos;
- não existir SQL, resultados, auditoria consultável ou MCP na interface;
- não houver finding novo sem tratamento e aprovação explícita.

### 7.3. Rollback

Desabilitar `MASKGW_ADMIN_UI_ENABLED` e reiniciar pelo lifecycle normal.

Confirmar:

- ausência das quatro rotas UI;
- rejeição por presença de Origin/Referer;
- headers e erros da Fase 7;
- funcionamento dos clientes administrativos nativos existentes.

Se necessário, retornar ao pacote anterior compatível, preservando a configuração persistida.

Desabilitar UI não desfaz adoção ou alterações confirmadas. Não restaurar automaticamente arquivos, IDs ou revision. Recuperação após durabilidade incerta, resultado desconhecido ou divergência disco/runtime continua sendo operação humana fora da UI.

## 8. Decisões aprovadas

Foram aprovadas integralmente as quatro decisões de produto/arquitetura:

1. **Entrega e fronteira:** UI embarcada opt-in, mesma origem, com política de navegador condicionada à flag e rollback para a Fase 7.
2. **Divisão público/privado:** aceitar o interpretador declarativo limitado, seu custo e a exposição residual explicitamente descrita.
3. **Escopo funcional:** CRUD granular; reorder somente de regras; SQL aditivo; ausência de substituição completa pela UI.
4. **Contrato operacional:** token/rascunhos apenas em memória, recuperação sem retry ou rollback automático e gates de tipagem, navegador e PostgreSQL reais.

As quatro decisões desta seção foram aprovadas integralmente em 2026-09-09. Nesta rodada, está autorizada exclusivamente a Etapa 1 documental e sua baseline. As Etapas 2–9, qualquer implementação funcional e qualquer publicação aguardam nova revisão e autorização explícita.
