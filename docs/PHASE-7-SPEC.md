# Fase 7 — Admin API · ESPECIFICAÇÃO FINAL

> **STATUS: PROPOSTA — AGUARDANDO APROVAÇÃO.**
>
> Nenhuma linha de código foi escrita. Não existe `src/maskgw/admin/`, não há
> FastAPI no `pyproject.toml`, não há teste. Este documento existe para ser
> revisado e aprovado **antes** de a implementação começar.
>
> Decisões que este documento implementa, sem reabrir: **D-047 a D-054**.

---

## 0. Resumo do que se propõe

Uma superfície administrativa HTTP, **no mesmo processo** do servidor MCP,
que gerencia o `masking.yaml` e reconstrói o runtime sem reiniciar o Gateway.

O que ela **não** é: um cliente de banco, um front-end, um plano de deployment
e um transporte MCP alternativo.

### Topologia

```text
┌─ processo único: python -m maskgw.mcp ──────────────────────────┐
│                                                                  │
│   thread principal            thread do admin (opcional)         │
│   MCP stdio  ──► Gateway      HTTP 127.0.0.1 ──► Admin API       │
│                     │                                 │          │
│                     └──── RuntimeRegistry ◄───────────┘          │
│                              (D-054)                             │
└──────────────────────────────────────────────────────────────────┘
```

O mesmo processo é obrigatório: a troca de runtime é uma reatribuição de
referência **em memória**. Um processo separado só poderia sinalizar um
restart, que é exatamente o que a Fase 7 existe para evitar.

**Consequência crítica do processo único:** `stdout` é o canal do protocolo
MCP. Qualquer byte escrito nele por uvicorn, por logging ou por um handler de
exceção **corrompe a sessão MCP**. Ver §10.4 — é requisito de implementação, não
recomendação.

---

## 1. Endpoints e operações permitidas

Prefixo único: `/admin/v1`. Nenhuma rota fora dele. Nenhuma rota implícita.

### 1.1 Leitura

| método | rota | devolve |
|---|---|---|
| `GET` | `/admin/v1/status` | revision, estado do runtime, secrets como `configured`/`missing`, contadores em memória |
| `GET` | `/admin/v1/config` | configuração administrativa completa + `revision` |
| `GET` | `/admin/v1/rules` | regras em ordem de avaliação, com `id` e `position` |
| `GET` | `/admin/v1/rules/{rule_id}` | uma regra |
| `GET` | `/admin/v1/exceptions` | exceptions, com `id` |
| `GET` | `/admin/v1/exceptions/{exception_id}` | uma exception |
| `GET` | `/admin/v1/transformers` | catálogo do registry: nome e parâmetros aceitos |
| `GET` | `/admin/v1/protected` | proteções estruturais, **somente leitura** (§11) |

### 1.2 Escrita

Todas exigem `expected_revision` no corpo, todas são serializadas na mesma
seção crítica administrativa (D-052), todas publicam `revision + 1`.

| método | rota | operação |
|---|---|---|
| `POST` | `/admin/v1/config:adopt` | migração única: atribui `id` a cada regra/exception e `revision: 1` (§5) |
| `POST` | `/admin/v1/config:validate` | **dry-run**: valida um candidato. Não compila, não conecta, não persiste, não altera revision |
| `PUT` | `/admin/v1/config` | substitui a configuração administrativa inteira |
| `POST` | `/admin/v1/rules` | cria uma regra (`position` opcional; default: fim) |
| `PUT` | `/admin/v1/rules/{rule_id}` | substitui uma regra por inteiro (sem PATCH) |
| `DELETE` | `/admin/v1/rules/{rule_id}` | remove uma regra |
| `POST` | `/admin/v1/rules:reorder` | recebe a lista completa de IDs na nova ordem |
| `POST` | `/admin/v1/exceptions` | cria uma exception |
| `PUT` | `/admin/v1/exceptions/{exception_id}` | substitui uma exception |
| `DELETE` | `/admin/v1/exceptions/{exception_id}` | remove uma exception |
| `PUT` | `/admin/v1/database` | só `statement_timeout_ms` e `max_rows` |
| `PUT` | `/admin/v1/sql` | só `allowed_pg_functions` e `denied_functions`, aditivos (§11) |
| `POST` | `/admin/v1/config:reload` | relê o arquivo do disco e reconstrói o runtime |

**Não há `PATCH`.** Merge parcial num documento de segurança é uma fonte de
ambiguidade sem contrapartida: o cliente já leu o objeto inteiro no `GET`.

**As exceptions não têm operação de reordenação.** A ordem entre regras é
semântica — *first match wins* (D-004) — mas entre exceptions não é: toda
exception que casa produz o mesmo desfecho, `ORIGINAL`. Criar uma operação de
reordenação para elas sugeriria uma semântica que não existe.

**Toda operação granular é açúcar.** Internamente ela é
`ler o documento inteiro → aplicar a mudança → validar o documento inteiro →
persistir → trocar`, dentro da mesma seção crítica. Não existe caminho de
escrita que altere o arquivo parcialmente.

### 1.3 O que não existe

Não existe, e não é apenas recusado — **a rota não é registrada** (D-049):

```text
/query   /sql   /execute   /explain   /schema   /tables   /preview
/secrets   /hmac-key   /token   /dsn   /database/dsn
/protected/*  (qualquer método de escrita)
```

Também não existem `/docs`, `/redoc` nem `/openapi.json`: o schema do FastAPI
seria entregue a um chamador não autenticado, descrevendo a superfície inteira.
Desligados na construção do app.

Verificado por teste estrutural (§12.7): o conjunto de rotas registradas é
comparado com a lista literal desta seção. Uma rota nova quebra o teste.

---

## 2. Autenticação administrativa mínima

**Um token estático, um papel, nenhuma sessão.**

| item | decisão |
|---|---|
| origem do token | `MASKGW_ADMIN_TOKEN`, variável de ambiente. Nunca no `masking.yaml`, nunca em argumento de linha de comando |
| tamanho mínimo | 32 caracteres, como a chave HMAC (D-006) |
| transporte | header `Authorization: Bearer <token>`, e **só** ele |
| comparação | `hmac.compare_digest` — tempo constante |
| ausência | com a Admin API habilitada e token ausente ou curto, **o processo não inicia** (fail-closed, como D-006) |
| habilitação | `MASKGW_ADMIN_ENABLED=1`. **Default: desabilitada.** Sem ela o processo é exatamente o de hoje, com zero superfície nova |

**O token nunca é aceito por query string nem por cookie.** Query string vaza
em log de proxy, em histórico e em `Referer`; cookie é o que torna CSRF
possível. Aceitar só o header é o que faz a proteção de §3 funcionar.

**A autenticação roda antes do parsing do corpo.** Um chamador sem token não
consegue distinguir um schema válido de um inválido: recebe `401` antes de o
Pydantic ver qualquer coisa. Sem isso, o 422 vira um oráculo de schema.

`401` é idêntico para token ausente, malformado e errado. Sem `WWW-Authenticate`
descritivo, sem "token expirado", sem contagem de tentativas na resposta.

**Fora de escopo, deliberadamente:** OAuth, OIDC, RBAC, múltiplos usuários,
papéis, expiração, refresh, rotação por API. A rotação do token é: trocar a
variável de ambiente e reiniciar. É honesto para um plano que escuta em
loopback e não tem front-end.

---

## 3. Bind, CORS e proteção contra chamadas indevidas

### 3.1 Bind

| variável | default | observação |
|---|---|---|
| `MASKGW_ADMIN_BIND` | `127.0.0.1` | loopback |
| `MASKGW_ADMIN_PORT` | `8765` | |

Um bind fora de loopback é **recusado no startup**, a menos que
`MASKGW_ADMIN_ALLOW_NONLOOPBACK=1` seja declarado explicitamente. Não há TLS,
não há autenticação além do token, e expor isso numa interface de rede é uma
decisão que precisa ser escrita, não herdada de um default.

### 3.2 CORS

**Nenhum header CORS é emitido. Nunca. Nem wildcard, nem lista.**

Não há preflight handler: `OPTIONS` não é registrado. Não existe front-end
nesta fase (Fase 8), então CORS não tem função — e um `Access-Control-Allow-
Origin: *` num plano administrativo permitiria que qualquer página aberta no
navegador do administrador lesse a configuração.

Quando a Fase 8 chegar, CORS será desenhado ali, explicitamente, com origem
única. Nunca por conveniência de desenvolvimento.

### 3.3 Proteção contra chamada indevida a partir do navegador

Uma API em `127.0.0.1` é alcançável por qualquer página que o administrador
abra. Quatro camadas, todas baratas:

1. **Token em header customizado.** Um `<form>` cross-origin não define
   headers; um `fetch` com `Authorization` dispara preflight, que não é
   respondido. Já basta sozinho — as demais existem porque "já basta sozinho"
   é o que se diz antes de descobrir a exceção.
2. **`Origin` ou `Referer` presentes → `403`.** Um cliente de API não envia
   esses headers; um navegador sempre envia.
3. **`Content-Type` diferente de `application/json` → `415`.** Um formulário
   HTML só consegue emitir `urlencoded`, `multipart` ou `text/plain`.
4. **`Host` fora da allowlist (`127.0.0.1:<porta>`, `localhost:<porta>`) →
   `400`.** Fecha DNS rebinding.

Complementos: corpo limitado a 1 MiB (`413` acima disso), nenhum arquivo
estático servido, nenhum redirecionamento seguido, nenhum upload.

---

## 4. Schemas de request e response

### 4.1 Regras gerais

- Pydantic v2, `extra="forbid"` e `frozen=True` em **todo** modelo de
  request e de response — o mesmo `_STRICT` de `config/models.py`.
- Nenhum `dict[str, Any]` atravessa a fronteira, em nenhuma direção. A única
  exceção herdada é `RuleConfig.config`, cujo conteúdo é validado pelo
  transformer alvo na compilação — e cuja validação passa a acontecer **antes**
  da persistência, não depois.
- Respostas são serializadas a partir do **modelo validado do arquivo**
  (`MaskingFileConfig` estendido), nunca dos objetos runtime (D-047). Um
  `RegexTransformer` carrega o padrão compilado, não o texto do YAML;
  reconstruir a partir dele devolveria algo parecido com a configuração, sem
  ser ela.
- Nenhum modelo é compartilhado com o plano MCP. Nenhum módulo de `admin/`
  importa `maskgw.mcp`, e vice-versa (verificado por teste de AST, §12.8).

### 4.2 A assimetria com o MCP, e por que ela é deliberada

No plano MCP, argumentos extras são **ignorados** pelo SDK — medido, aceito,
registrado (D-037, F-10). No plano administrativo eles são **recusados**.

Não é inconsistência: no MCP o extra é inofensivo porque o handler não o lê e a
garantia testada é que o resultado não muda. No admin, um extra é quase sempre
um cliente desatualizado escrevendo num campo que ele acha que existe — e
aceitar em silêncio significa uma configuração que não é a pretendida.

### 4.3 Forma do request de escrita

Todo corpo de escrita carrega:

```text
expected_revision : int   obrigatório, >= 0
<payload da operação>
```

### 4.4 Forma da resposta

Sucesso de escrita:

```text
revision   : int          a nova revision publicada
applied    : true
```

Leitura: o objeto pedido, sempre acompanhado de `revision`.

Erro: **sempre** a mesma forma, com um `error` de conjunto fechado (§10.2) e
um `detail` de texto **fixo por categoria**. Nunca a exceção, nunca o valor
submetido.

### 4.5 Erro de schema

O corpo de um `422` lista **caminhos de campo** e um código de motivo fechado
(`unknown_field`, `missing`, `out_of_range`, `wrong_type`, `too_short`).

**Nunca o valor submetido.** O handler default do FastAPI para
`RequestValidationError` inclui o `input` que falhou; ele é substituído. Isso
não é hipotético: um `fixed.value` ou um `regex.replacement` recusado voltaria
no corpo do erro e daí para o log do cliente.

---

## 5. IDs e migração da configuração atual

### 5.1 O ponto de partida

O `config/masking.yaml` de hoje não tem `id` nem `revision`, e é **comentado à
mão** — os comentários explicam por que `md5` não serve para CPF. E
`MaskingFileConfig` tem `extra="forbid"`: um arquivo com `revision:` hoje **não
carrega**.

### 5.2 Mudança de formato

Dois campos novos, ambos opcionais na leitura:

| campo | onde | default na ausência |
|---|---|---|
| `revision` | topo do documento | `0` |
| `id` | cada item de `masking` e de `exceptions` | ausente |

Um arquivo sem nenhum dos dois continua carregando e o MCP continua subindo,
sem Admin API, sem adoção, sem nada. **Esse é o requisito de compatibilidade,
e é um teste** (§12.9).

Formato do ID: `rul_<32 hex>` e `exc_<32 hex>`, aleatório na criação, opaco,
imutável pela vida do item. Editar uma regra preserva o ID; remover e recriar
gera outro. Não há renomeação.

O ID **não** substitui a ordem (D-051): `GET /rules` devolve `position`
derivado da ordem no arquivo, e a reordenação é operação própria.

### 5.3 Adoção — a migração, explícita e única

Antes da adoção:

- **leitura funciona.** `GET /config` responde com `adopted: false` e sem IDs.
- **escrita é recusada** com `409 CONFIG_NOT_ADOPTED`.

`POST /admin/v1/config:adopt` atribui os IDs, define `revision: 1` e persiste.

Duas exigências, porque a adoção reescreve um arquivo que um humano escreveu:

1. **`confirm_comment_loss: true` no corpo.** Uma volta por Pydantic e PyYAML
   **destrói os comentários** do YAML. Isso é irreversível e precisa ser dito
   antes, não descoberto depois.
2. **Backup automático** em `masking.yaml.bak.<epoch>`, no mesmo diretório,
   modo `0600`, escrito e `fsync`ado antes de qualquer escrita do arquivo real.

E a garantia que importa: **a adoção não pode mudar nenhuma decisão de
masking.** Verificada por teste comparando o veredito do engine, antes e
depois, sobre uma tabela de nomes de coluna (§12.9). ID e revision são
metadata administrativa; não participam do matching.

Por que não gerar IDs em memória a cada boot, sem adoção: eles mudariam a cada
restart, e um cliente que guardasse `rul_...` editaria outra regra depois de
um reinício. Um ID instável é pior que nenhum ID.

---

## 6. Semântica de `revision` e HTTP 409

`revision` é um inteiro monotônico, persistido **dentro** do próprio arquivo.
Fora dele, arquivo e revision divergiriam na janela de crash de §7.3 e o
controle otimista passaria a mentir depois de um restart.

Ciclo: `0` = não adotado · adoção publica `1` · cada escrita bem-sucedida
publica `atual + 1`. Nunca decresce, nunca é reutilizada, nunca é escolhida
pelo cliente.

### O que 409 significa

| condição | `error` |
|---|---|
| `expected_revision` ≠ revision atual | `REVISION_CONFLICT` |
| escrita antes da adoção | `CONFIG_NOT_ADOPTED` |
| runtimes aposentados demais ainda abertos (§8.5) | `RELOAD_BUSY` |

O corpo de `REVISION_CONFLICT` inclui `current_revision`, para o cliente
reler e reenviar. Não é vazamento: o mesmo chamador autenticado obtém o número
num `GET`.

**Em conflito, nada é escrito.** Nem arquivo, nem runtime, nem revision. A
comparação acontece **dentro** da seção crítica administrativa (D-052) — fora
dela, duas requisições leriam a mesma revision, ambas aprovariam a comparação,
e a segunda sobrescreveria a primeira, que já respondeu sucesso.

**Duas requisições com o mesmo `expected_revision` não vencem ambas.** Não há
ordem garantida entre elas; a garantia é que exatamente uma vence e a outra
recebe `409`. É um teste (§12.1).

---

## 7. Persistência atômica, permissões e recuperação de crash

### 7.1 A escrita

```text
1. abrir  .masking.yaml.<pid>.<rand>.tmp  no MESMO diretório, modo 0600 na criação
2. escrever o documento serializado
3. flush + os.fsync(fd)
4. close
5. os.replace(tmp, masking.yaml)          <- ponto de não-retorno
6. os.fsync(fd do DIRETÓRIO)              <- torna o próprio rename durável
```

O passo 6 é o que costuma faltar. Sem ele, o `rename` pode não ter chegado ao
disco quando a máquina cai, e o arquivo antigo reaparece — com a revision
antiga, depois de a API ter respondido sucesso.

Mesmo diretório é obrigatório: `os.replace` só é atômico dentro do mesmo
filesystem.

Falha em 1–4: o temporário é removido, **o arquivo anterior está intacto**,
`CONFIG_WRITE_ERROR`. Temporários órfãos de um crash anterior são removidos no
startup — nunca são lidos, porque só o nome final é lido.

### 7.2 Permissões

| arquivo | modo | verificação |
|---|---|---|
| `masking.yaml` escrito pelo Gateway | `0600` | na criação, não por `chmod` posterior |
| `masking.yaml` no startup | — | **gravável por grupo ou por outros → o processo não inicia** |
| backup de adoção | `0600` | |

Um `masking.yaml` gravável por terceiros é um bypass de masking com passo
único: quem pode escrever nele pode remover todas as regras. Isso é fatal, não
um aviso.

O arquivo não contém segredo algum — DSN, credenciais e chave HMAC continuam só
em env — então a **leitura** não é restringida além do que o operador escolher.

### 7.3 A janela de crash, e como o sistema se recupera

**Não há atomicidade conjunta entre filesystem e memória** (D-048). São dois
meios e nenhuma primitiva cobre os dois. O que existe é uma sequência cujo
ponto de não-retorno é conhecido:

| falha em | arquivo | runtime |
|---|---|---|
| validação, compilação, conexão, capability check | anterior | anterior |
| persistência (antes do `replace`) | **anterior** | anterior |
| **crash entre `replace` e swap** | **novo** | o processo morreu |
| swap | não falha parcialmente — é uma reatribuição de referência | |

**Depois do `replace`, o arquivo já é o novo, e não há rollback de arquivo.**
Este documento não afirma, em ponto algum, que "qualquer falha antes do swap
preserva o arquivo": a partir do `replace` isso é falso. Um rollback só poderia
ser afirmado se existisse com teste que o exercitasse; não existe.

**Recuperação na janela:** o próximo start lê o arquivo, que é o novo, e sobe
com ele. Não há reconciliação, não há arquivo a reverter, não há estado
corrompido — o documento persistido é exatamente aquele que passou por
validação, compilação, conexão e capability check **antes** de ser escrito. É
por isso que a verificação vem antes da persistência: não é otimização, é o que
torna a janela recuperável.

**O que o administrador precisa saber:** uma operação que não retornou sucesso
pode ter tomado efeito no próximo start. Após qualquer queda durante uma
operação administrativa, **leia a configuração vigente antes de repetir**. O
Gateway registra no startup a revision que carregou, para essa comparação.

---

## 8. Lifecycle e refcount dos runtimes (D-054)

### 8.1 O objeto

`Runtime` é **imutável** e agrega: `revision`, modelo do arquivo, config
compilada, `MaskingEngine`, `SqlPolicy`, `DatabaseSettings`, `PostgresAdapter`
e o lock de conexão daquele adapter (D-034). Trocar de runtime é reatribuir
uma referência.

Estado mutável, e só ele: `refcount`, `retired`, `closed`.

### 8.2 Operações

| operação | sob o lock de ciclo de vida | fora do lock |
|---|---|---|
| `acquire()` | lê a referência publicada, incrementa | — |
| `release(rt)` | decrementa; decide se cabe fechar | fecha o adapter |
| `swap(novo)` | aposenta o antigo, publica o novo, decide se cabe fechar | fecha o antigo, se couber |

O `close` do adapter roda **fora** da seção crítica: fechar uma conexão psycopg
pode demorar, e segurar o lock durante isso bloquearia a aquisição de toda
query nova.

### 8.3 As seis regras, textualmente

1. **O reload não bloqueia esperando queries antigas.** Publica, aposenta,
   decide, retorna.
2. **O runtime antigo é marcado `retired` no swap**, sob o mesmo lock que
   publica o novo.
3. **Aquisição, swap, refcount e decisão de fechamento usam a mesma
   sincronização.** Todas leem ou escrevem o par `(retired, refcount)`; uma
   decisão tomada sobre leitura parcial fecha um runtime em uso ou vaza um
   aposentado.
4. **O último release fecha o runtime aposentado exatamente uma vez.** A
   condição — `retired` e `refcount == 0` e ainda não `closed` — é avaliada sob
   o lock, que também marca `closed`. Não há "verificar e depois fechar" fora
   do lock.
5. **Se o antigo já estiver sem usuários no swap, é fechado ali mesmo.** É o
   caso comum, o Gateway ocioso. Sem esta regra ele nunca fecharia: não haverá
   release algum para disparar o fechamento.
6. **Nenhuma query adquire um runtime aposentado.** A aquisição lê a referência
   publicada e incrementa sob o mesmo lock; um aposentado já não é a referência
   publicada. Se alguma via alcançar um runtime com `retired`, ela não o
   adquire e não o usa.

### 8.4 Três locks, que não se confundem

| lock | cobre | duração |
|---|---|---|
| administrativo (D-052) | `expected_revision`, nova revision, persistência, swap | a operação administrativa inteira |
| de ciclo de vida (D-054) | aquisição, swap, refcount, decisão de fechamento | uma transição de estado |
| de conexão (D-034) | a conexão psycopg de **um** runtime | a execução da query |

Nenhum deles cobre a execução de query no reload. Serializar queries numa
operação administrativa transformaria um reload num stall do Gateway inteiro.

### 8.5 Limite de runtimes aposentados abertos

Cada runtime aposentado segura **uma conexão PostgreSQL** até seu último
usuário sair. Reloads sucessivos com queries longas empilhariam conexões.

Limite: **4** runtimes aposentados abertos simultaneamente. Um reload que
excederia o limite é recusado com `409 RELOAD_BUSY` — o runtime candidato é
fechado e nada muda. O teto natural de vida de um aposentado continua sendo o
`statement_timeout` (D-028).

---

## 9. O que a Admin API pode e não pode alterar

### 9.1 Editável

`masking[*]` (match, mode, case_sensitive, transformer, config) ·
`exceptions[*]` (match, mode, case_sensitive) · ordem das regras ·
`database.statement_timeout_ms` · `database.max_rows` ·
`sql.allowed_pg_functions` e `sql.denied_functions`, **aditivamente**.

### 9.2 Por que o candidato reconecta

`database.statement_timeout_ms` viaja em `options` do DSN (D-028) e só vale a
partir de uma sessão nova. Por isso o fluxo de D-048 conecta e verifica —
read-only, `statement_timeout` conferido em `pg_settings`, capability de
provenance — **antes** de persistir. Um timeout que o servidor recuse falha
ali, com o runtime antigo intacto.

**O DSN não é campo administrativo.** Credenciais, host e banco continuam
vindo só de secret/env, não são editáveis e não são retornados. A reconexão usa
o mesmo DSN de sempre.

---

## 10. Sanitização de erros

### 10.1 A regra

**Nunca `str(exc)`. Nunca traceback. `__cause__` e `__context__` nulos.**

O erro sanitizado é levantado **fora** do bloco `except` (D-017). `raise ...
from None` zera `__cause__` mas o interpretador ainda pendura a original em
`__context__` quando o `raise` ocorre dentro de um handler ativo. Esse trap já
foi introduzido duas vezes neste projeto e pego por teste nas duas.

### 10.2 Categorias, fechadas

```text
UNAUTHORIZED · NOT_FOUND · SCHEMA_INVALID · CONFIG_INVALID
REVISION_CONFLICT · CONFIG_NOT_ADOPTED · CONFIG_WRITE_ERROR
CONFIG_RELOAD_ERROR · RELOAD_BUSY · IMMUTABLE_FIELD · INTERNAL_ERROR
```

`detail` é texto **fixo por categoria**. `CONFIG_INVALID` e `SCHEMA_INVALID`
podem citar **caminhos de campo**, nunca valores.

Um erro do PostgreSQL durante a verificação do candidato vira
`CONFIG_RELOAD_ERROR` — a mensagem original pode embutir valores
(`invalid input syntax for type integer: "..."`) e não sai, exatamente como no
plano MCP.

### 10.3 Handlers substituídos

Três handlers default do FastAPI/Starlette são trocados, e os três importam:

| handler | por que trocar |
|---|---|
| `RequestValidationError` | o default inclui o valor `input` que falhou |
| `HTTPException` | o default ecoa `detail` arbitrário |
| `Exception` (catch-all) | sem ele, uma exceção inesperada sobe para o servidor, que registra o traceback antes de responder — o mesmo motivo de D-038 no MCP |

### 10.4 Logging — `stdout` é do MCP

`audit/` continua sendo o **único** módulo autorizado a importar `logging`. O
módulo `admin/` **não** importa `logging`: registra através de `audit/`,
estendido com um registro administrativo. O teste global existente é estendido,
nunca afrouxado.

E, como `stdout` é o canal do protocolo MCP:

- uvicorn é configurado **sem** os handlers default; `access_log` desligado
- todo log do processo vai para `stderr`
- nenhum `print` em `admin/`
- teste: com a Admin API ativa e sob carga administrativa, uma sessão MCP
  completa não vê byte estranho em `stdout`

---

## 11. Secrets, e o que é somente leitura

### 11.1 Secrets: `configured` ou `missing`, nada mais

`GET /admin/v1/status` devolve:

```text
secrets:
  hmac_sha256_key : "configured" | "missing"
  admin_token     : "configured"
  database_dsn    : "configured" | "missing"
```

Nunca o valor. Nunca o tamanho, o prefixo, os últimos caracteres, um hash, uma
data de criação ou o host contido no DSN. **Não existe endpoint que defina ou
rotacione um secret** — rotação é env + restart.

Campos como `password`, `dsn`, `host`, `hmac_key` já são fatais no loader e
seriam recusados por `extra="forbid"`; além disso, são teste explícito.

### 11.2 Proteções estruturais — visíveis, nunca editáveis (D-050)

`GET /admin/v1/protected` **exibe**, e nenhuma rota altera:

- `denied_relations`: `pg_statistic`, `pg_stats`, `pg_stats_ext`,
  `pg_stats_ext_exprs`, `pg_statistic_ext`, `pg_statistic_ext_data` (D-039,
  fechou o finding F-05, CRITICAL)
- as quatro regras do validator: um statement executável, raiz `SelectStmt`,
  nenhum outro `*Stmt`, `IntoClause`/`LockingClause` recusadas (D-031)
- `pg_` deny-by-default e as denylists estruturais (D-027)
- sessão read-only e capability de provenance (D-026, D-028, D-040)
- a ordem do pipeline: `DERIVED → EXCEPTION → MASKING → ORIGINAL`
- o default ALLOW

**Campos que não existem** — não recusados, inexistentes: `read_only`,
`allow_multiple_statements`, `disable_sql_validation`, `disable_masking`,
`unmatched_policy`, `denied_relations`, `denied_prefixes`.

### 11.3 O caso concreto de `allowed_pg_functions`

Hoje `SqlPolicy.allows` avalia, nesta ordem: `denied_functions` →
`denied_prefixes` → allowlist do namespace `pg_`. Como `pg_read_file` **não**
está em `DEFAULT_DENIED_FUNCTIONS` nem casa um prefixo negado, uma
configuração com `sql.allowed_pg_functions: ["pg_read_file"]` **o libera**.

No arquivo isso é uma edição local de quem já é dono da máquina. Pela Admin API
seria uma chamada HTTP que reabre leitura de arquivos do servidor — exatamente
o que D-050 proíbe.

Portanto: um conjunto **nunca-liberável** rejeita, com `IMMUTABLE_FIELD`,
qualquer `allowed_pg_functions` que contenha acesso a arquivo, execução de
programa, controle de backend, replicação ou leitura de configuração —
`pg_read_file`, `pg_read_binary_file`, `pg_ls_*`, `pg_stat_file`,
`pg_terminate_backend`, `pg_cancel_backend`, `pg_reload_conf`, `pg_sleep*`,
famílias `pg_*_wal_*` e de replicação, entre outras. A lista literal entra na
especificação de implementação e é dado imutável, não configuração.

> **Questão aberta para aprovação (§14.2):** aplicar o mesmo conjunto
> nunca-liberável também ao **carregamento do arquivo**, e não apenas à Admin
> API. Fecharia o mesmo buraco na porta de entrada, mas é mudança de
> comportamento do produto atual e não pertence à Fase 7 sem decisão explícita.

---

## 12. Testes exigidos

Nenhuma parte da Fase 7 é considerada concluída sem estes. Bypass conhecido
vira teste que o afirma, nunca `skip` (D-041).

### 12.1 Concorrência administrativa
- N escritas paralelas com o mesmo `expected_revision`: **exatamente um** `200`,
  N−1 `409`; revision final = inicial + 1; o arquivo contém a mudança vencedora
  e só ela.
- Escritas concorrentes em rotas diferentes (rules, exceptions, database): o
  arquivo final é sempre um documento válido de uma única operação.
- Escrita administrativa concorrente com queries MCP: nenhuma query falha.

### 12.2 Reload com queries em voo
- Query iniciada antes do swap termina com a política **antiga**, sem erro e
  sem interrupção.
- Query iniciada depois do swap usa a política **nova**.
- Nenhuma query é abortada por fechamento de conexão.

### 12.3 Refcount e ciclo de vida
- O adapter aposentado é fechado **exatamente uma vez** (adapter falso que
  conta chamadas de `close`).
- Nunca fechado com `refcount > 0`.
- `refcount == 0` no swap → fechado **imediatamente**, sem depender de release.
- Aquisição nunca devolve um runtime `retired` (teste com swap forçado no meio
  da aquisição).
- Sem vazamento: após K reloads e todas as queries terminadas, K adapters
  fechados.
- Além de 4 aposentados abertos → `RELOAD_BUSY`, candidato fechado, nada muda.

### 12.4 Rollback / injeção de falha
Uma falha injetada em **cada** passo — validação, compilação, conexão,
capability check, escrita do temporário, `fsync`, `replace` — e para cada uma:
- bytes do arquivo **idênticos** aos de antes (comparação byte a byte);
- o runtime publicado é o **mesmo objeto** de antes (identidade, não igualdade);
- o adapter candidato foi fechado;
- a categoria de erro é a esperada;
- `__cause__` e `__context__` nulos.

### 12.5 Janela de crash
- Exceção injetada **entre** `replace` e swap: o arquivo em disco é o documento
  novo, completo e válido; um `build_application` novo sobre ele sobe e reporta
  a revision nova.
- Nenhum arquivo parcial é legível em nenhum instante (leitor concorrente
  durante a escrita só vê o documento antigo ou o novo, nunca metade).
- Temporário órfão presente no startup é removido e nunca é lido.

### 12.6 Leakage
- Token, chave HMAC e DSN não aparecem em nenhum corpo de resposta, header,
  registro de auditoria ou mensagem de erro — inclusive nos caminhos de erro.
- `repr` da app, do registry e do runtime não contêm secret.
- Nenhuma resposta de erro carrega `str(exc)`, traceback, ou cadeia de exceção.
- Uma sessão MCP não vê byte estranho em `stdout` com o admin ativo.

### 12.7 Bypass e superfície
- O conjunto de rotas registradas é **igual** à lista de §1 — teste por
  enumeração. Rota nova quebra o teste.
- `/query`, `/sql`, `/execute`, `/docs`, `/openapi.json`, `/redoc` → `404`.
- Sem token → `401`; token errado → `401`; token em query string → `401`.
- `Origin` presente → `403`; `Content-Type: text/plain` → `415`; `Host` alheio
  → `400`; corpo > 1 MiB → `413`.
- Nenhum header CORS em nenhuma resposta, inclusive nas de erro.
- Toda tentativa de alterar proteção estrutural → `IMMUTABLE_FIELD` ou rota
  inexistente; `allowed_pg_functions` com nome nunca-liberável → recusado.
- `401` chega **antes** de qualquer `422`: um chamador sem token não consegue
  sondar o schema.

### 12.8 Separação de planos
- Teste de AST, no estilo de `test_purity.py`: nenhum módulo de `admin/`
  importa `maskgw.mcp`; nenhum de `mcp/` importa `maskgw.admin`.
- `admin/` não importa `logging` (extensão do teste global existente).
- `masking/` continua puro: importar `maskgw.masking` não carrega `admin/`,
  FastAPI nem psycopg.

### 12.9 Migração
- O `config/masking.yaml` atual, sem `id` e sem `revision`, carrega; o MCP sobe.
- Escrita antes da adoção → `409 CONFIG_NOT_ADOPTED`.
- Adoção sem `confirm_comment_loss` → recusada.
- Adoção grava o `.bak` antes de tocar no arquivo real.
- **A adoção não altera nenhuma decisão de masking**: veredito do engine
  idêntico, antes e depois, sobre uma tabela de nomes de coluna que cubra
  regra, exception, alias e coluna sem correspondência.
- Adoção é idempotente na segunda chamada: recusada, não repetida.

---

## 13. Escopo de auditoria

### 13.1 O limite atual, declarado

`audit/` emite metadata estruturada via `logging` e **não tem armazenamento
consultável**. Não existe histórico para responder.

Consequência direta: **a Fase 7 não terá `GET /admin/v1/audit/*` devolvendo
histórico.** Um endpoint desses precisaria de um store — arquivo indexado ou
banco — com retenção, rotação e um modelo de acesso próprio. Isso é uma fase
inteira, e inventá-la aqui entregaria um endpoint que mente.

### 13.2 O que a Fase 7 acrescenta

Um registro administrativo emitido **através de `audit/`** por operação:

```text
request_id · operation · outcome · revision_before · revision_after
duration_ms · error_category
```

**O que não entra no registro:** corpo da requisição, padrões de regra, nomes
de coluna, valores de transformer, token, qualquer secret.

A exclusão dos **padrões de regra** é consistência com D-035 e com
`docs/SECURITY.md`: nomes de coluna não são registrados porque um nome pode ser
revelador — e o `match` de uma regra é um nome de coluna. Registra-se o `id` da
regra e a operação, que é o que permite correlacionar sem revelar.

### 13.3 Contadores em memória

`GET /admin/v1/status` pode expor contadores desde o start do processo —
revision atual, runtimes aposentados abertos, contagem de queries e de
operações administrativas. **São contadores, não histórico**, e se perdem no
restart. O status diz isso explicitamente no seu próprio schema.

Um store de auditoria consultável entra em `docs/FUTURE-HARDENING.md` como
proposta com custo, não como pendência da Fase 7.

---

## 14. Confirmações e questões abertas

### 14.1 Confirmado, sem ambiguidade

| item | confirmação |
|---|---|
| execução de SQL pela Admin API | **não existe** — D-049, verificado por teste de enumeração de rotas |
| front-end | **não** — é a Fase 8, e depende desta |
| deployment | **não** — sem TLS, sem proxy reverso, sem systemd, sem Docker; é a Fase 9 |
| HTTP MCP | **não** — MCP continua stdio only (D-036). A porta administrativa é outro plano e não transporta MCP |
| MCP altera configuração | **não** — não há, e não haverá, superfície MCP para isso |
| handler ou schema compartilhado entre os planos | **não** — verificado por teste de AST |
| DSN como campo administrativo | **não** — só secret/env, nem para leitura |
| `enabled` por regra | **não** nesta versão (D-053) |
| FastAPI no `pyproject.toml` | **só quando esta especificação for aprovada** |

### 14.2 Questões que precisam de decisão antes da implementação

1. **Conjunto nunca-liberável também no carregamento do arquivo?** (§11.3)
   Fecha o mesmo buraco na porta de entrada, mas muda o comportamento do
   produto atual. Recomendação: sim, em fase própria — não silenciosamente
   junto com a Fase 7.
2. **Limite de 4 runtimes aposentados** (§8.5): é um número escolhido, não
   medido. Confirmar ou substituir.
3. **Porta default `8765`**: arbitrária. Confirmar.
4. **A adoção destrói os comentários do `config/masking.yaml`** (§5.3). O
   backup e a confirmação explícita mitigam, não evitam. Se os comentários
   forem considerados patrimônio do projeto, a alternativa é mover a
   configuração administrada para outro caminho — ao custo de duas fontes de
   verdade, que é pior. Recomendação: aceitar a perda, com backup.

---

## 15. Ordem de implementação proposta

Cada etapa termina com suíte verde, `ruff` e `mypy --strict` limpos. Nenhuma
começa antes de a anterior fechar.

| # | etapa | fecha |
|---|---|---|
| 1 | `revision` e `id` opcionais nos modelos; compatibilidade do arquivo atual | §5.2, §12.9 |
| 2 | `RuntimeRegistry`: imutabilidade, refcount, `retired`, fechamento único | §8, §12.3 |
| 3 | Gateway passa a adquirir/liberar runtime por query | §8.2, §12.2 |
| 4 | Persistência atômica com `fsync` de diretório, permissões, limpeza de temporários | §7, §12.4, §12.5 |
| 5 | Seção crítica administrativa e o fluxo de D-048 fim a fim | §6, §12.1 |
| 6 | App HTTP: auth, bind, anti-CSRF, handlers de erro, rotas de leitura | §2, §3, §10 |
| 7 | Rotas de escrita e adoção | §1.2, §5.3 |
| 8 | Registro administrativo em `audit/` | §13 |
| 9 | Suíte adversarial administrativa | §12.6, §12.7, §12.8 |

Se qualquer etapa revelar que uma decisão aqui está errada, ela volta para
aprovação antes de o código seguir. Não se avança de fase com teste falhando,
nem sem aprovação.
