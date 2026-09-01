# Fase 7 — Admin API · ESPECIFICAÇÃO FINAL

> **STATUS: APROVADA PARA IMPLEMENTAÇÃO.**
>
> Aprovada sobre o commit `923b3b291dc2fcdb97fe31984b5d57fa00a7c041`. A
> implementação segue **estritamente** este documento; qualquer incompatibilidade
> real entre ele e a arquitetura existente interrompe a implementação e volta
> para decisão, em vez de ser resolvida reduzindo garantia (§15).
>
> Decisões que este documento implementa, sem reabrir: **D-047 a D-054**.
>
> **Estado da implementação.** Etapas 1–5 concluídas. A Etapa 5 implementa os
> primitivos de §7.1–§7.3 e §7.5 em `maskgw/config/filesystem.py`, sem compor a
> seção crítica, runtime candidato ou HTTP. A Etapa 6 é a próxima e não foi
> iniciada.
>
> **Histórico.** Primeira versão em `dcf497f`, com quatro questões abertas.
> Esta revisão registra as quatro decisões (§14) e corrige dez bloqueios
> levantados na revisão: `allowed_pg_functions` somente leitura, limite de um
> runtime aposentado, `config:reload` removido, semântica de falha depois do
> `replace`, escritor único por lock de arquivo, segurança de filesystem, bind
> só loopback, lifecycle de startup/shutdown, composition root e `AdminAudit`
> fechado.

---

## 0. Resumo do que se propõe

Uma superfície administrativa HTTP, **no mesmo processo** do servidor MCP,
que gerencia o `masking.yaml` e reconstrói o runtime sem reiniciar o Gateway.

O que ela **não** é: um cliente de banco, um front-end, um plano de deployment
e um transporte MCP alternativo.

### Topologia

```text
┌─ processo único: python -m maskgw ──────────────────────────────┐
│                                                                  │
│                    composition root  (§9)                        │
│                    conhece os dois planos                        │
│                   ┌──────────┴──────────┐                        │
│   thread principal│                     │thread do admin         │
│   MCP stdio ──► Gateway          Admin API ◄── HTTP 127.0.0.1    │
│                    │                     │                       │
│                    └── RuntimeRegistry ──┘                       │
│                          (D-054)                                 │
└──────────────────────────────────────────────────────────────────┘
```

O mesmo processo é obrigatório: a troca de runtime é uma reatribuição de
referência **em memória**. Um processo separado só poderia sinalizar um
restart, que é exatamente o que a Fase 7 existe para evitar.

**Consequência crítica:** `stdout` é o canal do protocolo MCP. Qualquer byte
escrito nele por uvicorn, por logging ou por um handler de exceção **corrompe a
sessão MCP**. Ver §10.4 — é requisito com teste, não recomendação.

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
| `GET` | `/admin/v1/protected` | proteções estruturais, **somente leitura** (§11.2) |

### 1.2 `config:validate` — a exceção deliberada

`POST /admin/v1/config:validate` tem corpo e usa `POST`, mas **não é uma
escrita**. É a única operação com corpo que não entra no fluxo de persistência.

| faz | não faz |
|---|---|
| exige autenticação, como toda rota | **não** conecta ao PostgreSQL |
| valida o schema do documento candidato | **não** persiste |
| **compila os transformers e a policy** | **não** altera `revision` |
| devolve os erros que a compilação encontrar | **não** publica `revision + 1` |
| | **não** entra na seção crítica administrativa |
| | **não** aposenta nem cria runtime |

Compilar, e não só validar o schema, é o ponto: um `regex` com padrão inválido,
um transformer inexistente ou um parâmetro ausente só aparecem na compilação.
Um dry-run que parasse no schema aprovaria configuração que a escrita real
recusaria — e seria pior que não existir.

**Não conecta** porque conectar tem custo e efeito no servidor, e porque a
verificação de conexão pertence ao fluxo real (D-048), onde há um candidato a
publicar. Consequência declarada: `config:validate` **não** consegue prever
falha de `statement_timeout_ms` recusado pelo servidor nem perda de catálogo.
Ele responde por schema e compilação, e diz isso na própria resposta.

**Não aceita `expected_revision`.** O resultado é função exclusiva do documento
submetido; nada é lido do estado nem escrito nele. Aceitar o campo sugeriria
uma garantia de concorrência que a operação não presta — entre o `validate` e a
escrita real, qualquer coisa pode acontecer. Enviado, é recusado por
`extra="forbid"`.

### 1.3 Escrita

Todas exigem `expected_revision`, todas são serializadas na mesma seção crítica
administrativa (D-052), todas publicam `revision + 1`, todas percorrem o fluxo
de §7.4 por inteiro.

| método | rota | operação |
|---|---|---|
| `POST` | `/admin/v1/config:adopt` | migração única: atribui `id` e `revision: 1` (§5) |
| `PUT` | `/admin/v1/config` | substitui a configuração administrativa inteira |
| `POST` | `/admin/v1/rules` | cria uma regra (`position` opcional; default: fim) |
| `PUT` | `/admin/v1/rules/{rule_id}` | substitui uma regra por inteiro |
| `DELETE` | `/admin/v1/rules/{rule_id}` | remove uma regra |
| `POST` | `/admin/v1/rules:reorder` | lista completa de IDs na nova ordem |
| `POST` | `/admin/v1/exceptions` | cria uma exception |
| `PUT` | `/admin/v1/exceptions/{exception_id}` | substitui uma exception |
| `DELETE` | `/admin/v1/exceptions/{exception_id}` | remove uma exception |
| `PUT` | `/admin/v1/database` | só `statement_timeout_ms` e `max_rows` |
| `PUT` | `/admin/v1/sql` | só `denied_functions`, aditivo (§11.3) |

**Não há `PATCH`.** Merge parcial num documento de segurança é ambiguidade sem
contrapartida: o cliente já leu o objeto inteiro no `GET`.

**As exceptions não têm reordenação.** A ordem entre regras é semântica —
*first match wins* (D-004) — mas entre exceptions não é: toda exception que casa
produz o mesmo desfecho, `ORIGINAL`.

**Toda operação granular é açúcar.** Internamente é `ler o documento inteiro →
aplicar a mudança → validar o documento inteiro → persistir → trocar`, na mesma
seção crítica. Não existe caminho que altere o arquivo parcialmente.

### 1.4 `config:reload` — removido da primeira versão

**Não existe.** Estava na versão anterior e sai.

Toda escrita administrativa já reconstrói o runtime, então o endpoint só
serviria para adotar uma edição manual externa — e é aí que ele cria
ambiguidade entre três coisas que precisam coincidir: a `revision` do arquivo,
a `revision` do runtime publicado, e uma edição feita fora da API que pode ter
mantido a revision antiga, repetido uma revision já usada ou pulado números.
Nenhuma resposta a esse conflito é obviamente correta, e o controle otimista de
D-052 deixaria de significar o que diz.

**Edição manual externa exige restart.** É a regra, e é simples de verificar.

Em contrapartida, uma edição externa nunca é silenciosamente sobrescrita:
§7.5 verifica, antes de qualquer escrita, se o arquivo em disco ainda
corresponde ao runtime publicado, e recusa com `409 CONFIG_OUT_OF_SYNC`.

### 1.5 O que não existe

A rota não é registrada — não é recusada, inexiste (D-049):

```text
/query   /sql   /execute   /explain   /schema   /tables   /preview
/secrets   /hmac-key   /token   /dsn   /database/dsn
/config:reload
/protected/*  (qualquer método de escrita)
```

Também não existem `/docs`, `/redoc` nem `/openapi.json`: entregariam a
superfície inteira a um chamador não autenticado. Desligados na construção.

Verificado por teste estrutural (§12.7): o conjunto de rotas registradas é
comparado com a lista literal desta seção.

---

## 2. Autenticação administrativa mínima

**Um token estático, um papel, nenhuma sessão.**

| item | decisão |
|---|---|
| origem | `MASKGW_ADMIN_TOKEN`. Nunca no `masking.yaml`, nunca em argumento de linha de comando |
| tamanho mínimo | 32 caracteres, como a chave HMAC (D-006) |
| transporte | header `Authorization: Bearer <token>`, e **só** ele |
| comparação | `hmac.compare_digest` — tempo constante |
| ausência | com a Admin API habilitada e token ausente ou curto, **o processo não inicia** |
| habilitação | `MASKGW_ADMIN_ENABLED=1`. **Default: desabilitada** — sem ela o processo é exatamente o de hoje |

**Nunca aceito por query string nem por cookie.** Query string vaza em log de
proxy, em histórico e em `Referer`; cookie é o que torna CSRF possível. Aceitar
só o header é o que faz §3.3 funcionar.

**A autenticação roda antes do parsing do corpo.** Sem token, o chamador recebe
`401` antes de o Pydantic ver qualquer coisa — senão o `422` vira oráculo de
schema.

`401` idêntico para token ausente, malformado e errado.

**Fora de escopo:** OAuth, OIDC, RBAC, múltiplos usuários, papéis, expiração,
refresh, rotação por API. Rotação é trocar a variável e reiniciar.

---

## 3. Bind, CORS e proteção contra chamadas indevidas

### 3.1 Bind — somente loopback

| variável | default | valores aceitos |
|---|---|---|
| `MASKGW_ADMIN_BIND` | `127.0.0.1` | `127.0.0.1`, `::1`, `localhost` |
| `MASKGW_ADMIN_PORT` | `8765` | 1..65535 |

**Qualquer endereço fora de loopback faz o processo recusar o startup.** Não há
opt-in, não há variável de escape: `MASKGW_ADMIN_ALLOW_NONLOOPBACK` foi
**removida** desta especificação.

O motivo é direto: não há TLS. Um bind em interface externa põe o bearer token
em HTTP claro, em todo request, na rede. Bind externo — com TLS, com um modelo
de autenticação que sobreviva a ele — pertence à **Fase 9**, junto com o resto
do problema de deployment.

Porta default **8765**, aprovada.

### 3.2 CORS

**Nenhum header CORS é emitido. Nunca. Nem wildcard, nem lista.** `OPTIONS` não
é registrado; não há preflight handler.

Não existe front-end nesta fase, então CORS não tem função — e um
`Access-Control-Allow-Origin: *` num plano administrativo deixaria qualquer
página aberta no navegador do administrador ler a configuração.

Quando a Fase 8 chegar, CORS será desenhado ali, com origem única. Nunca por
conveniência de desenvolvimento.

### 3.3 Proteção contra chamada indevida a partir do navegador

Uma API em `127.0.0.1` é alcançável por qualquer página que o administrador
abra. Quatro camadas, todas baratas:

1. **Token em header customizado.** Um `<form>` cross-origin não define
   headers; um `fetch` com `Authorization` dispara preflight, não respondido.
2. **`Origin` ou `Referer` presentes → `403`.** Cliente de API não os envia;
   navegador sempre envia.
3. **`Content-Type` ≠ `application/json` em método com corpo → `415`.** Um
   formulário HTML só emite `urlencoded`, `multipart` ou `text/plain`.
4. **`Host` fora da allowlist (`127.0.0.1:<porta>`, `localhost:<porta>`,
   `[::1]:<porta>`) → `400`.** Fecha DNS rebinding.

---

## 4. Schemas de request e response

### 4.1 Regras gerais

- Pydantic v2, `extra="forbid"` e `frozen=True` em **todo** modelo de request e
  de response — o mesmo `_STRICT` de `config/models.py`.
- Nenhum `dict[str, Any]` atravessa a fronteira. A exceção herdada é
  `RuleConfig.config`, validada pelo transformer alvo na compilação — que passa
  a acontecer **antes** da persistência, não depois.
- Respostas serializadas a partir do **modelo validado do arquivo**, nunca dos
  objetos runtime (D-047).
- Nenhum modelo compartilhado com o plano MCP. Nenhum módulo de `admin/`
  importa `maskgw.mcp`, e vice-versa (teste de AST, §12.8).

### 4.2 A assimetria com o MCP, deliberada

No MCP, argumentos extras são **ignorados** pelo SDK (D-037, F-10). No admin
são **recusados**. No MCP o extra é inofensivo porque o handler não o lê; no
admin, um extra é quase sempre um cliente desatualizado escrevendo num campo
que ele acha que existe — e aceitar em silêncio produz uma configuração que não
é a pretendida.

### 4.3 Forma do request de escrita

```text
expected_revision : int   obrigatório, >= 0
<payload da operação>
```

### 4.4 Forma da resposta

Sucesso de escrita: `revision` (a nova) e `applied: true`.

Leitura: o objeto pedido, sempre com `revision`.

Erro: sempre a mesma forma, com `error` de conjunto fechado (§10.2) e `detail`
de texto **fixo por categoria**. Uma única categoria carrega `applied: true` —
`CONFIG_DURABILITY_ERROR` (§7.6), e a razão está lá.

### 4.5 Erro de schema

O corpo de um `422` lista **caminhos de campo** e um código de motivo fechado
(`unknown_field`, `missing`, `out_of_range`, `wrong_type`, `too_short`,
`immutable`).

**Nunca o valor submetido.** O handler default do FastAPI para
`RequestValidationError` inclui o `input` que falhou; ele é substituído. Não é
hipotético: um `fixed.value` ou um `regex.replacement` recusado voltaria no
corpo do erro e daí para o log do cliente.

---

## 5. IDs e migração da configuração atual

### 5.1 O ponto de partida

O `config/masking.yaml` de hoje não tem `id` nem `revision`, e é **comentado à
mão**. E `MaskingFileConfig` tem `extra="forbid"`: um arquivo com `revision:`
hoje **não carrega**.

### 5.2 Mudança de formato

| campo | onde | default na ausência |
|---|---|---|
| `revision` | topo do documento | `0` |
| `id` | cada item de `masking` e de `exceptions` | ausente |

Um arquivo sem nenhum dos dois continua carregando e o MCP continua subindo,
sem Admin API e sem adoção. **É o requisito de compatibilidade, e é teste**
(§12.9).

**Esclarecimento do estado adotado na Etapa 1:** quando `revision >= 1`, toda
regra e toda exception precisa ter `id`. Se qualquer item estiver sem `id`, a
configuração é inconsistente e **falha no carregamento**. Isso explicita a
coerência entre os dois metadados já aprovados: não cria um novo estado nem
altera a semântica de adoção; impede que o processo suba num estado em que as
escritas exigiriam adoção, mas `config:adopt` já não poderia partir de
`expected_revision: 0`.

Formato: `rul_<32 hex>` e `exc_<32 hex>`, aleatório na criação, opaco, imutável
pela vida do item. Editar preserva o ID; remover e recriar gera outro. Não há
renomeação.

O ID **não** substitui a ordem (D-051): `GET /rules` devolve `position`
derivado da ordem no arquivo; reordenar é operação própria.

### 5.3 Adoção — a migração, explícita e única

Antes da adoção: **leitura funciona** (`adopted: false`, sem IDs); **toda
escrita que não seja a própria adoção é recusada** com
`409 CONFIG_NOT_ADOPTED`.

`POST /admin/v1/config:adopt` atribui os IDs, define `revision: 1` e persiste.

**Exige estado não adotado e `expected_revision: 0`** — é a única escrita que
parte de `0`, e a única cuja pré-condição é o estado *não* adotado (§7.4.1).
Sobre uma configuração já adotada é **recusada com
`409 CONFIG_ALREADY_ADOPTED`, sem alteração alguma**: nada escrito, nenhum
backup criado, nenhum ID regerado, revision intacta.

**Exige `confirm_comment_loss: true`.** Uma volta por Pydantic e PyYAML
**destrói os comentários** do YAML. É irreversível e precisa ser dito antes.

### 5.4 O backup, e o que ele garante

Antes de qualquer escrita do arquivo real, a adoção grava
`masking.yaml.bak.<epoch>` no mesmo diretório:

- **exatamente os bytes originais**, copiados byte a byte. Não é uma
  reserialização do modelo: uma reserialização já teria perdido os comentários,
  que é justamente o que o backup existe para preservar;
- **criação exclusiva** (`O_CREAT | O_EXCL`) e **modo `0600` na criação**;
- **`fsync` do arquivo** antes de prosseguir;
- **nunca sobrescreve um backup existente.** Se o nome colidir, a adoção
  **falha** com `CONFIG_WRITE_ERROR` e nada é tocado. Falhar é o comportamento
  correto: sobrescrever um backup é destruir o único registro dos comentários.

**Onde os comentários passam a viver:** no arquivo de backup e na documentação
do projeto. O `masking.yaml` passa a ser um documento gerido por máquina, e o
conteúdo dos comentários atuais — por que `md5` não serve para CPF, por que a
chave HMAC não pode estar no arquivo — já está em `docs/MASKING-SPEC.md` e em
`docs/SECURITY.md`, que continuam sendo a fonte. Um comentário reintroduzido à
mão no `masking.yaml` será perdido na escrita administrativa seguinte, sem
aviso; essa é a consequência aceita.

### 5.5 A garantia que importa

**A adoção não pode mudar nenhuma decisão de masking.** Verificada por teste
comparando o veredito do engine, antes e depois, sobre uma tabela de nomes de
coluna (§12.9). ID e revision são metadata administrativa e não participam do
matching.

Por que não gerar IDs em memória a cada boot, sem adoção: mudariam a cada
restart, e um cliente que guardasse `rul_...` editaria outra regra depois de um
reinício. Um ID instável é pior que nenhum ID.

---

## 6. Semântica de `revision` e HTTP 409

`revision` é um inteiro monotônico, persistido **dentro** do próprio arquivo.
Fora dele, arquivo e revision divergiriam na janela de crash de §7.7.

Ciclo: `0` = não adotado · adoção publica `1` · cada escrita publica
`atual + 1`. Nunca decresce, nunca é reutilizada, nunca é escolhida pelo
cliente.

### O que 409 significa

| condição | `error` |
|---|---|
| `expected_revision` ≠ revision atual | `REVISION_CONFLICT` |
| escrita antes da adoção | `CONFIG_NOT_ADOPTED` |
| `config:adopt` sobre configuração já adotada | `CONFIG_ALREADY_ADOPTED` |
| arquivo em disco divergiu do runtime publicado | `CONFIG_OUT_OF_SYNC` |
| já existe um runtime aposentado em uso | `RELOAD_BUSY` |

O corpo de `REVISION_CONFLICT` inclui `current_revision`. Não é vazamento: o
mesmo chamador autenticado obtém o número num `GET`.

**Em conflito, nada é escrito.** A comparação acontece **dentro** da seção
crítica (D-052): fora dela, duas requisições leriam a mesma revision, ambas
aprovariam, e a segunda sobrescreveria a primeira, que já respondeu sucesso.

**Duas requisições com o mesmo `expected_revision` não vencem ambas.** Sem
ordem garantida entre elas; a garantia é que exatamente uma vence. É teste
(§12.1).

---

## 7. Persistência, filesystem e recuperação

### 7.1 Um único escritor: lock de arquivo

O lock administrativo de D-052 é `threading.Lock`: protege threads **do mesmo
processo**. Dois processos apontando para o mesmo `masking.yaml` se
sobrescreveriam sem que nenhum dos dois notasse.

Com a Admin API habilitada, o processo **adquire um lock exclusivo de arquivo
no startup e o mantém por toda a sua vida**. Um segundo processo administrativo
sobre o mesmo arquivo **falha no startup** com `CapabilityError`, antes de
abrir a porta e antes de servir MCP.

**O lock não é sobre o `masking.yaml`.** É sobre um `masking.yaml.lock` ao lado
dele, criado uma vez, modo `0600`, **nunca renomeado e nunca substituído**.
A razão é concreta: `os.replace` troca o inode do `masking.yaml`, e um lock
mantido sobre o arquivo de configuração passaria, depois da primeira escrita, a
proteger um inode que ninguém mais alcança. O lock ficaria válido e inútil.

| plataforma | mecanismo | semântica |
|---|---|---|
| POSIX | `fcntl.flock(fd, LOCK_EX \| LOCK_NB)` | **advisory**: vale entre processos que também pedem o lock. Liberado pelo fim do processo, inclusive por `SIGKILL`. Não é confiável sobre NFS |
| Windows | `msvcrt.locking(fd, LK_NBLCK, 1)` | byte-range **mandatório**: outro processo que tente bloquear a mesma faixa falha. Liberado no fechamento do handle |

Em ambas, um crash libera o lock — não há lock órfão a limpar.

**O lock não cobre editores humanos.** `vim`, `sed` e um `cp` não pedem lock
algum, e no POSIX nada os impede. É exatamente por isso que §7.5 existe: o lock
resolve o caso de dois Gateways, e o `CONFIG_OUT_OF_SYNC` **detecta** o caso do
editor. Nenhum dos dois substitui o outro, e nenhum dos dois é absoluto — ver
§7.5.2.

#### O arquivo de lock recebe as mesmas proteções do arquivo de configuração

`masking.yaml.lock` é um arquivo controlado pelo Gateway e é um alvo tão bom
quanto o `masking.yaml`: um symlink no lugar dele redirecionaria a abertura, e
um lock que qualquer um possa substituir não é lock.

| verificação | quando |
|---|---|
| **não seguir symlink** (`os.lstat`, e `O_NOFOLLOW` onde a plataforma o oferece) | sempre |
| **exigir arquivo regular** (`S_ISREG`) | sempre |
| **modo `0600`** | na criação; e conferido ao reutilizar |
| **criação exclusiva** (`O_CREAT \| O_EXCL`) | quando ainda não existe |
| **validar tipo e permissões ANTES de abrir para lock** | quando já existe |

Reutilizar um lock preexistente é o caso normal — ele sobrevive ao processo. A
validação de tipo e permissões acontece **antes** da abertura para o lock, não
depois: abrir primeiro e verificar depois já teria seguido o symlink.

O **file descriptor permanece aberto por toda a vida do processo**. Fechá-lo
libera o lock em ambas as plataformas; guardá-lo não é detalhe de
implementação, é o mecanismo.

#### Filesystem suportado: local

**A persistência atômica e o lock exigem filesystem local.** As duas dependem
de garantias que sistemas de arquivos em rede não prestam de forma confiável:

- `flock` sobre **NFS** não é confiável — dependendo de versão, montagem e
  implementação do servidor, ele pode ser local ao cliente, silenciosamente
  ineficaz entre máquinas, ou não suportado;
- a atomicidade de `os.replace` e a durabilidade do `fsync` de diretório
  variam com a implementação do servidor e as opções de montagem.

**Configuração administrável em NFS, SMB/CIFS, ou em qualquer filesystem com
semântica equivalente, não é suportada na Fase 7.** Não há detecção automática
e não há bloqueio no startup: é uma condição de suporte declarada, não um
mecanismo. Um Gateway sem Admin API — o modo default — não é afetado, porque
não escreve.

#### Windows: bits POSIX e ACL não são a mesma coisa

As verificações de permissão desta especificação são sobre **bits de modo
POSIX** (`S_IWGRP`, `S_IWOTH`) e sobre a criação com modo `0600`.

No Windows esses bits **não** têm equivalência com o modelo de segurança real,
que é de ACLs. O Python expõe uma emulação limitada: `os.stat` devolve bits
sintéticos, e o modo passado na criação afeta pouco mais que o atributo
somente-leitura. Uma ACL permissiva num diretório pode deixar o arquivo
gravável por terceiros **com os bits POSIX parecendo corretos**.

Portanto, declarado sem eufemismo: **no Windows, a implementação não valida
ACLs, e esta especificação não promete que valide.** As verificações de tipo
(symlink, arquivo regular) e o lock por byte-range continuam valendo; a
verificação de permissão é, ali, best-effort. Restringir o acesso ao diretório
de configuração é responsabilidade operacional nessa plataforma.

### 7.2 Segurança do filesystem, antes de administrar

Verificado no startup, com a Admin API habilitada. Qualquer item que falhe
**impede o processo de subir**:

| verificação | por quê |
|---|---|
| `masking.yaml` **não** é symlink (`os.lstat`) | um symlink redireciona a escrita para fora do diretório controlado |
| `masking.yaml` é **arquivo regular** (`S_ISREG`) | FIFO, device ou socket no lugar do arquivo |
| `masking.yaml` **não** é gravável por grupo nem por outros | quem escreve nele remove todas as regras — bypass de masking em um passo |
| **diretório pai** não é gravável por grupo nem por outros | quem escreve no diretório substitui o arquivo por `rename`, sem tocar no arquivo |

Aberturas usam `O_NOFOLLOW` onde a plataforma o oferece (POSIX). No Windows
não há equivalente direto; a checagem por `lstat` permanece, e a diferença é
declarada, não escondida.

Temporários e backups: `O_CREAT | O_EXCL`, modo `0600` **na criação** — nunca
`chmod` depois, que deixa uma janela.

**Limpeza de temporários órfãos:** somente arquivos que casem o padrão exato
gerado pelo Gateway — `.masking.yaml.tmp.<pid>.<16 hex>` — no diretório de
configuração, e que sejam arquivos regulares não-symlink. **Nenhum glob amplo**:
um `*.tmp` apagaria arquivo de terceiro no mesmo diretório. Órfãos nunca são
lidos: só o nome final é lido.

### 7.3 A escrita atômica

```text
1. abrir  .masking.yaml.tmp.<pid>.<16 hex>  no MESMO diretório,
          O_CREAT|O_EXCL|O_WRONLY, modo 0600
2. escrever o documento serializado
3. flush + os.fsync(fd do arquivo)
4. close
5. os.replace(tmp, masking.yaml)          <── PONTO DE NÃO-RETORNO
6. fsync do DIRETÓRIO                      (POSIX; ver §7.6)
```

Mesmo diretório é obrigatório: `os.replace` só é atômico dentro do mesmo
filesystem.

**Estratégia de `fsync`, por plataforma:**

| passo | POSIX | Windows |
|---|---|---|
| `fsync` do arquivo temporário (3) | `os.fsync(fd)` | `os.fsync(fd)` — mapeia para `FlushFileBuffers` |
| `fsync` do diretório (6) | abrir o diretório com `O_RDONLY` e `os.fsync` | **não existe**: não se abre diretório como arquivo |

No Windows o passo 6 é **omitido**, e a consequência é declarada: a durabilidade
do próprio `rename` fica por conta do sistema de arquivos. `os.replace` continua
atômico (`MoveFileEx` com `MOVEFILE_REPLACE_EXISTING`) — o que não se garante é
que ele já esteja em disco após uma queda de energia. Os dois `fsync` são
testados **separadamente** (§12.5), porque falham em pontos diferentes da linha
e têm consequências diferentes.

### 7.4 O fluxo completo de uma escrita

Tudo dentro da seção crítica administrativa (D-052):

```text
 1. estado de adoção compatível com a
    operação                                -> 409 CONFIG_NOT_ADOPTED
                                               409 CONFIG_ALREADY_ADOPTED
 2. expected_revision confere               -> 409 REVISION_CONFLICT
 3. arquivo em disco confere com o runtime  -> 409 CONFIG_OUT_OF_SYNC   (§7.5)
 4. nenhum runtime aposentado em uso        -> 409 RELOAD_BUSY          (§8.5)
 5. aplicar a mudança; validar o documento  -> CONFIG_INVALID
 6. compilar e construir o runtime candidato-> CONFIG_RELOAD_ERROR
 7. conectar e verificar read-only,
    statement_timeout e provenance          -> CONFIG_RELOAD_ERROR
 8. persistir atomicamente (passos 1–5)     -> CONFIG_WRITE_ERROR
 9. fsync do diretório                      -> CONFIG_DURABILITY_ERROR  (§7.6)
10. swap: aposentar o antigo, publicar o
    novo, atualizar o digest de referência
11. fechar o aposentado se refcount == 0
```

Os passos 1–4 são **todos anteriores** a construir e conectar. Nenhum recurso é
criado para uma operação que já se sabe que vai falhar, e nenhuma conexão nova é
aberta para ser fechada em seguida.

### 7.4.1 O passo 1 é assimétrico: `config:adopt` é o inverso das demais

O passo 1 **não** é "exigir estado adotado". Se fosse, `config:adopt` nunca
poderia rodar — ela existe justamente para sair do estado não adotado.

| operação | exige | `expected_revision` | se a condição falhar |
|---|---|---|---|
| `POST /config:adopt` | estado **NÃO adotado** | **exatamente `0`** | `409 CONFIG_ALREADY_ADOPTED` |
| **todas as demais escritas** | estado **adotado** | `>= 1`, igual à atual | `409 CONFIG_NOT_ADOPTED` |

Consequências, explícitas:

- `config:adopt` sobre uma configuração **já adotada** é **recusada, sem
  alteração alguma**: nada é escrito, nenhum backup é criado, nenhum ID é
  regerado, a `revision` não muda. É o que torna a adoção idempotente na
  recusa, e não na repetição — reexecutá-la trocaria todos os IDs, que é
  exatamente o que D-051 existe para impedir.
- `config:adopt` com `expected_revision` diferente de `0` é recusada com
  `409 REVISION_CONFLICT` no passo 2, como qualquer outra escrita.
- **Depois da adoção, `revision` passa de `0` para `1`.** É a única transição
  em que a revision de origem é `0`; daí em diante toda escrita parte de
  `>= 1`.

Os dois caminhos — adotar quando cabe, e recusar quando já foi adotado — são
teste (§12.9).

### 7.5 `CONFIG_OUT_OF_SYNC` — o arquivo mudou por fora

O Gateway guarda o **digest SHA-256 dos bytes exatos** a partir dos quais o
runtime publicado foi construído. No passo 3, relê o arquivo e recalcula.

Divergiu → **`409 CONFIG_OUT_OF_SYNC`, e nada é sobrescrito.** A recuperação é
manual e explícita: o administrador decide se a edição externa vale (e então
reinicia o processo, §1.4) ou se deve ser descartada.

Isso cobre o editor que não respeita o lock de §7.1. Digest de conteúdo, e não
`mtime` ou tamanho: `mtime` tem granularidade grosseira e é falsificável por
`touch`, e uma edição pode preservar o tamanho.

O digest é atualizado no passo 10, junto com o swap, a partir dos bytes que
acabaram de ser escritos.

### 7.5.1 Duas verificações, e o que elas realmente garantem

Uma verificação só no passo 3 deixaria descoberto todo o intervalo entre ela e
o `os.replace` — validação, compilação, conexão e capability check, que é a
parte demorada da operação. Um editor externo que escrevesse ali teria seu
trabalho sobrescrito sem que nada notasse.

Por isso o digest é conferido **duas vezes**:

| # | quando | o que cobre |
|---|---|---|
| 1ª | passo 3, no início | edição ocorrida antes da operação começar |
| 2ª | **imediatamente antes de `os.replace`** | edição ocorrida durante validação, compilação, conexão e verificação do candidato |

Divergência em qualquer uma das duas → `409 CONFIG_OUT_OF_SYNC`, o candidato é
fechado, o temporário é removido e **nada é sobrescrito**.

### 7.5.2 O que isto NÃO garante

Esta especificação não afirma exclusão mútua contra um editor não cooperante.
O que existe, com precisão:

- **O lock de arquivo (§7.1) garante exclusão entre processos Gateway
  cooperantes.** Dois Gateways não escrevem no mesmo arquivo. É a garantia
  forte, e é a única.
- **A segunda verificação detecta edição externa ocorrida durante a maior
  parte da operação** — todo o intervalo entre o passo 3 e o `replace`. É
  detecção, não prevenção.
- **Não existe CAS portátil de arquivo.** Nenhuma primitiva POSIX ou Windows
  oferece "substitua este caminho somente se o conteúdo ainda for este", de
  forma atômica e portátil. Entre a segunda leitura do digest e o `os.replace`
  resta uma janela, curta, que nenhuma técnica portátil fecha.
- **Portanto:** não se afirma que um editor rodando com o mesmo usuário jamais
  poderá vencer essa última janela. Ele pode. A afirmação honesta é que a
  janela é curta e que qualquer edição fora dela é detectada.

**Editar o `masking.yaml` à mão enquanto uma escrita administrativa está em
curso é operação não suportada na Fase 7.** O caminho suportado para edição
manual é: parar o processo, editar, reiniciar (§1.4).

A corrida real — arquivo alterado entre a primeira verificação e o `replace` —
é teste (§12.5).

### 7.6 Depois do `replace`: três situações, não uma

**Não existe atomicidade conjunta entre filesystem e memória** (D-048). O
ponto de não-retorno é o `os.replace`, e a especificação não afirma nada
diferente de nenhum dos lados dele.

| momento | arquivo | runtime | resposta |
|---|---|---|---|
| falha **antes** de `os.replace` | **anterior, intacto** | anterior | `CONFIG_WRITE_ERROR`, `applied` ausente |
| `os.replace` **concluído** | **novo, instalado** | ainda o antigo | segue para 9 |
| falha no **`fsync` do diretório** | **novo** — depois do não-retorno | ver abaixo | `CONFIG_DURABILITY_ERROR`, `applied: true` |
| crash entre `replace` e swap | **novo** | o processo morreu | nenhuma — §7.7 |

**Falha do `fsync` do diretório não pode afirmar rollback**, porque o arquivo
novo já está instalado. Desfazê-lo exigiria reescrever o anterior — outra
escrita, com o mesmo risco, sobre um estado já incerto.

Comportamento definido:

1. **O runtime novo é publicado** (passo 10 acontece). Memória e arquivo ficam
   coerentes, que é a única propriedade ainda alcançável.
2. A resposta é `CONFIG_DURABILITY_ERROR`, HTTP `500`, com **`applied: true`** e
   `current_revision` — a nova. O administrador precisa saber as duas coisas: a
   mudança **valeu**, e a durabilidade dela **não está confirmada**.
3. O erro é registrado por `audit/` como categoria, **sem a mensagem original**
   (§10.1).

Sobre o `500` com `applied: true`: um cliente que retente por reflexo não causa
dano — seu `expected_revision` já está velho e ele recebe
`409 REVISION_CONFLICT`, sem sobrescrever nada. A ação correta continua sendo
reler o estado, e a resposta diz isso.

### 7.7 A janela de crash entre persistir e trocar

Se o processo morrer entre o `replace` e o swap: em disco, a configuração nova,
já validada, já compilada e já comprovada conectável; em memória, nada.

**Recuperação:** o próximo start lê o arquivo, que é o novo, e sobe com ele.
Não há reconciliação, não há arquivo a reverter, não há estado corrompido — o
documento persistido é exatamente o que passou por validação, compilação,
conexão e capability check **antes** de ser escrito. É por isso que a
verificação vem antes da persistência: não é otimização, é o que torna a janela
recuperável.

**O que o administrador precisa saber:** uma operação que não retornou sucesso
pode ter tomado efeito no próximo start. Após qualquer queda durante uma
operação administrativa, **leia a configuração vigente antes de repetir**. O
Gateway registra no startup a revision que carregou.

---

## 8. Lifecycle e refcount dos runtimes (D-054)

### 8.1 O objeto

`Runtime` é **imutável** e agrega: `revision`, modelo do arquivo, config
compilada, `MaskingEngine`, `SqlPolicy`, `DatabaseSettings`, `PostgresAdapter`
e o lock de conexão daquele adapter (D-034). Trocar de runtime é reatribuir uma
referência.

Estado mutável, e só ele: `refcount`, `retired`, `closed`.

### 8.2 Operações

| operação | sob o lock de ciclo de vida | fora do lock |
|---|---|---|
| `acquire()` | lê a referência publicada, incrementa | — |
| `release(rt)` | decrementa; decide se cabe fechar | fecha o adapter |
| `swap(novo)` | aposenta o antigo, publica o novo, decide se cabe fechar | fecha o antigo, se couber |

O `close` roda **fora** da seção crítica: fechar uma conexão psycopg pode
demorar, e segurar o lock durante isso bloquearia toda query nova.

### 8.3 As seis regras

1. **O reload não bloqueia esperando queries antigas.** Publica, aposenta,
   decide, retorna.
2. **O antigo é marcado `retired` no swap**, sob o mesmo lock que publica o novo.
3. **Aquisição, swap, refcount e decisão de fechamento usam a mesma
   sincronização.** Todas leem ou escrevem `(retired, refcount)`; decisão sobre
   leitura parcial fecha runtime em uso ou vaza aposentado.
4. **O último release fecha o aposentado exatamente uma vez.** A condição —
   `retired` e `refcount == 0` e não `closed` — é avaliada sob o lock, que
   também marca `closed`.
5. **Se o antigo já estiver sem usuários no swap, é fechado ali mesmo.** É o
   caso comum, o Gateway ocioso. Sem esta regra ele nunca fecharia: não haverá
   release algum para disparar.
6. **Nenhuma query adquire um runtime aposentado.** A aquisição lê a referência
   publicada e incrementa sob o mesmo lock; um aposentado já não é a referência
   publicada. Se alguma via alcançar um `retired`, não o adquire.

### 8.4 Três locks, que não se confundem

| lock | cobre | duração |
|---|---|---|
| administrativo (D-052) | `expected_revision`, digest, revision, persistência, swap | a operação administrativa inteira |
| de ciclo de vida (D-054) | aquisição, swap, refcount, decisão de fechamento | uma transição de estado |
| de conexão (D-034) | a conexão psycopg de **um** runtime | a execução da query |

Nenhum deles cobre execução de query no reload.

### 8.5 Limite: **um** runtime aposentado

Cada aposentado segura **uma conexão PostgreSQL** até seu último usuário sair.

**Limite: 1.** Se já existe um aposentado ainda em uso, um novo reload é
recusado com **`409 RELOAD_BUSY`** — e a verificação é o **passo 4** de §7.4,
**antes** de compilar, construir e conectar o candidato. Nada é criado para ser
descartado, e nenhuma conexão nova é aberta para uma operação já condenada.

O invariante que isso produz, e que é teste (§12.3):

```text
conexões PostgreSQL simultâneas <= 2
(o runtime publicado + no máximo um aposentado ainda em uso)
```

#### Quanto tempo um aposentado vive

**Não há teto absoluto, e o `statement_timeout` não é um.**

`statement_timeout` (D-028) limita a **execução do statement dentro do
PostgreSQL**. Ele não limita o que vem antes nem o que vem depois, e é o
conjunto disso que segura a referência:

- bloqueio de rede entre o cliente e o servidor;
- o `fetchmany` em lotes até a última linha (D-018);
- canonicalização por valor (D-015);
- masking por célula;
- serialização da resposta e sua entrega pelo MCP;
- um cliente que pare de consumir, ou que trave.

**A regra é uma só: o aposentado vive até a query liberar a referência.** Não
até o `statement_timeout` expirar.

Consequência prática, declarada: **o limite de um aposentado impede o
crescimento do número de conexões, mas não limita a duração de um
`RELOAD_BUSY`.** Enquanto uma query não terminar e liberar a referência, todo
reload continua sendo recusado — potencialmente por muito mais tempo que o
`statement_timeout`. O que a Fase 7 garante é o teto de conexões, não a
disponibilidade da operação administrativa.

---

## 9. Composição dos planos

A Fase 7 exige processo único **e** exige que `mcp/` não conheça `admin/`.
As duas coisas convivem por uma **composition root** fora dos dois.

```text
runtime/      RuntimeRegistry: acquire, release, swap, retired, refcount
              não importa admin/, não importa mcp/, não importa gateway/

gateway/      usa runtime.acquire / runtime.release por query
admin/        usa runtime.swap; não importa mcp/
mcp/          usa gateway; não importa admin/

bootstrap/    <- COMPOSITION ROOT
              o ÚNICO módulo que importa admin/ e mcp/ ao mesmo tempo;
              constrói o registry, o runtime inicial, o app admin e o
              servidor MCP, e conduz startup e shutdown (§9.2)
```

`RuntimeRegistry` fica em `runtime/`, abaixo dos dois planos, porque ambos
precisam dele com papéis diferentes: o data plane adquire e libera, o admin
plane troca. Pô-lo em `gateway/` ou em `admin/` forçaria uma dependência na
direção errada.

**Nenhum handler e nenhum schema são compartilhados** (D-049 e a separação de
planos de `docs/ARCHITECTURE.md`). O bootstrap conhece os dois; nenhum dos dois
conhece o outro. É teste de AST (§12.8), no estilo de `test_purity.py`.

`python -m maskgw.mcp` continua funcionando e passa a delegar ao bootstrap.

### 9.2 Startup e shutdown

**Startup, nesta ordem, e falha em qualquer passo termina o processo com
código 1:**

```text
1. ler e validar MASKGW_ADMIN_ENABLED, MASKGW_ADMIN_TOKEN (>= 32),
   MASKGW_ADMIN_BIND (só loopback) e MASKGW_ADMIN_PORT
2. verificações de filesystem de §7.2
3. adquirir o lock exclusivo de arquivo (§7.1)
4. construir o runtime inicial: config, compilação, adapter, read-only,
   statement_timeout, capability de provenance
5. iniciar a thread do servidor admin
6. AGUARDAR a confirmação de que o socket está efetivamente escutando,
   com timeout; falha ou timeout => o processo NÃO sobe
7. só então disponibilizar o MCP em stdio
8. registrar em stderr a revision carregada
```

O passo 6 é o que impede o pior caso: se o MCP subisse antes, o Gateway
atenderia queries por um tempo e então morreria por uma porta ocupada — com o
administrador convencido de que a Admin API está no ar. Confirmar o **bind**, e
não a partida da thread, porque uvicorn escuta de forma assíncrona.

**Shutdown, nesta ordem:**

```text
1. parar de aceitar novas queries MCP
2. sinalizar o servidor admin e AGUARDAR (join) a thread HTTP terminar
3. fechar o runtime publicado e todos os aposentados
4. liberar o lock de arquivo
5. nenhuma thread daemon abandonada: toda thread criada tem join no shutdown
```

Aguardar a thread HTTP **antes** de fechar os runtimes é o que impede uma
requisição administrativa em voo de tentar um swap sobre um registry já
desmontado.

Em todo o ciclo: **nenhum byte em `stdout`** (§10.4).

---

## 10. Sanitização de erros

### 10.1 A regra

**Nunca `str(exc)`. Nunca traceback. `__cause__` e `__context__` nulos.**

O erro sanitizado é levantado **fora** do bloco `except` (D-017). `raise ...
from None` zera `__cause__`, mas o interpretador ainda pendura a original em
`__context__` quando o `raise` ocorre dentro de um handler ativo. Esse trap já
foi introduzido duas vezes neste projeto e pego por teste nas duas.

### 10.2 Categorias, fechadas

```text
UNAUTHORIZED · NOT_FOUND · SCHEMA_INVALID · CONFIG_INVALID
REVISION_CONFLICT · CONFIG_NOT_ADOPTED · CONFIG_ALREADY_ADOPTED
CONFIG_OUT_OF_SYNC · RELOAD_BUSY
CONFIG_WRITE_ERROR · CONFIG_DURABILITY_ERROR · CONFIG_RELOAD_ERROR
IMMUTABLE_FIELD · INTERNAL_ERROR
```

`detail` é texto **fixo por categoria**. `CONFIG_INVALID` e `SCHEMA_INVALID`
podem citar **caminhos de campo**, nunca valores. `CONFIG_DURABILITY_ERROR` é a
única que acompanha `applied: true` (§7.6).

Um erro do PostgreSQL durante a verificação do candidato vira
`CONFIG_RELOAD_ERROR`: a mensagem original pode embutir valores
(`invalid input syntax for type integer: "..."`) e não sai — como no plano MCP.

### 10.3 Handlers substituídos

| handler | por que trocar |
|---|---|
| `RequestValidationError` | o default inclui o valor `input` que falhou |
| `HTTPException` | o default ecoa `detail` arbitrário |
| `Exception` (catch-all) | sem ele a exceção sobe para o servidor, que registra o traceback antes de responder — o motivo de D-038 no MCP |

### 10.4 Logging — `stdout` é do MCP

`audit/` continua sendo o **único** módulo autorizado a importar `logging`.
`admin/` **não** importa `logging`: registra através de `audit/` (§13). O teste
global existente é estendido, nunca afrouxado.

E, como `stdout` é o canal do protocolo:

- uvicorn configurado **sem** os handlers default; `access_log` desligado
- todo log do processo vai para `stderr`
- nenhum `print` em `admin/` nem em `bootstrap/`
- teste: com a Admin API ativa e sob carga administrativa, uma sessão MCP
  completa não vê byte estranho em `stdout`

---

## 11. Secrets, e o que é somente leitura

### 11.1 Secrets: `configured` ou `missing`

```text
secrets:
  hmac_sha256_key : "configured" | "missing"
  admin_token     : "configured"
  database_dsn    : "configured" | "missing"
```

Nunca o valor. Nunca tamanho, prefixo, últimos caracteres, hash ou data.
**Não existe endpoint que defina ou rotacione um secret** — rotação é env +
restart. Campos como `password`, `dsn`, `host`, `hmac_key` já são fatais no
loader, seriam recusados por `extra="forbid"`, e além disso são teste.

### 11.2 Proteções estruturais — visíveis, nunca editáveis (D-050)

`GET /admin/v1/protected` **exibe**, e nenhuma rota altera:

- `denied_relations`: `pg_statistic`, `pg_stats`, `pg_stats_ext`,
  `pg_stats_ext_exprs`, `pg_statistic_ext`, `pg_statistic_ext_data` (D-039,
  fechou F-05, CRITICAL)
- as quatro regras do validator (D-031)
- `pg_` deny-by-default, `denied_prefixes` e **`allowed_pg_functions`** (§11.3)
- sessão read-only e capability de provenance (D-026, D-028, D-040)
- a ordem do pipeline: `DERIVED → EXCEPTION → MASKING → ORIGINAL`
- o default ALLOW

**Campos que não existem** — não recusados, inexistentes: `read_only`,
`allow_multiple_statements`, `disable_sql_validation`, `disable_masking`,
`unmatched_policy`, `denied_relations`, `denied_prefixes`.

### 11.3 `allowed_pg_functions` é somente leitura

**Decisão: o campo inteiro sai da superfície administrativa.**

O motivo está medido em `sql/policy.py`. `SqlPolicy.allows` avalia
`denied_functions` → `denied_prefixes` → allowlist do namespace `pg_`. Como
`pg_read_file` **não** está em `DEFAULT_DENIED_FUNCTIONS` nem casa prefixo
negado, `sql.allowed_pg_functions: ["pg_read_file"]` **o libera**. No arquivo
isso é edição de quem já é dono da máquina; por HTTP seria reabrir leitura de
arquivos do servidor por chamada de API — o que D-050 proíbe.

Consequências, exatas:

- **`PUT /sql` edita apenas `denied_functions`**, aditivamente. Negação só
  restringe: acrescentar uma negação nunca abre nada.
- **`PUT /sql` e `PUT /config` não podem acrescentar, remover nem alterar
  `allowed_pg_functions`.** O campo presente no corpo → **`IMMUTABLE_FIELD`**.
  Ausente → o **valor semântico atual** — conteúdo e ordem da lista — é
  carregado para o documento candidato **sem alteração**, a partir do
  documento persistido. Um `PUT /config` nunca o apaga por omissão.

  **Não se promete preservação byte a byte deste trecho**, e não seria
  possível prometer: `PUT /config` reserializa o YAML inteiro, então aspas,
  indentação, quebra de linha e ordem das chaves do documento podem mudar. O
  que se garante é o **valor validado**: a lista que o candidato carrega é
  igual, em conteúdo e em ordem, à que o documento persistido carregava. É
  assim que o teste compara (§12.7) — modelo validado contra modelo validado,
  nunca fatia de texto contra fatia de texto.

  A garantia **byte a byte** continua valendo em um único lugar desta
  especificação: o backup dos bytes originais da adoção (§5.4).
- **`GET /config` e `GET /protected` mostram o valor**, como leitura.
- **Não existe a lista administrativa "nunca-liberável"** que a versão anterior
  propunha. Ela existia para peneirar um campo administrável; com o campo
  inteiro fora da administração, ela vira código morto com aparência de
  proteção — pior que não ter.

**O comportamento do loader não muda nesta fase.** Um operador com acesso ao
arquivo continua podendo escrever `allowed_pg_functions: ["pg_read_file"]`, e
o Gateway continua aceitando. Endurecer o loader é **proposta separada**, com
sua própria aprovação, porque muda o comportamento de um produto já entregue.
Registrado em `docs/FUTURE-HARDENING.md`, não implícito aqui.

---

## 12. Testes exigidos

Nenhuma parte da Fase 7 é concluída sem estes. Bypass conhecido vira teste que
o afirma, nunca `skip` (D-041).

### 12.1 Concorrência administrativa
- N escritas paralelas com o mesmo `expected_revision`: **exatamente um** `200`,
  N−1 `409`; revision final = inicial + 1; o arquivo contém a mudança vencedora
  e só ela.
- Escritas concorrentes em rotas diferentes: o arquivo final é sempre um
  documento válido de uma única operação.
- Escrita administrativa concorrente com queries MCP: nenhuma query falha.
- **Segundo processo** com Admin API sobre o mesmo arquivo: falha no startup,
  não abre porta, não serve MCP (§7.1). Testado por subprocesso real.

### 12.2 Reload com queries em voo
- Query iniciada antes do swap termina com a política **antiga**, sem erro.
- Query iniciada depois do swap usa a política **nova**.
- Nenhuma query é abortada por fechamento de conexão.

### 12.3 Refcount e ciclo de vida
- Adapter aposentado fechado **exatamente uma vez** (adapter falso que conta
  `close`).
- Nunca fechado com `refcount > 0`.
- `refcount == 0` no swap → fechado **imediatamente**, sem depender de release.
- Aquisição nunca devolve `retired` (swap forçado no meio da aquisição).
- **Limite 1:** com um aposentado em uso, novo reload → `409 RELOAD_BUSY`,
  **e nenhum adapter candidato foi construído nem conectado** — verificado por
  contador de tentativas de conexão, não só por ausência de erro.
- **O total de conexões não cresce:** K reloads sob carga contínua, com
  amostragem do número de adapters abertos, `máximo <= 2` em todo o intervalo, e
  K−1 fechados ao final com todas as queries terminadas.

### 12.4 Rollback e falha injetada

**Falhas ANTES de `os.replace`** — validação, compilação, conexão, capability
check, criação do temporário, escrita, `fsync` do temporário. Para cada uma:
- bytes do arquivo **idênticos** aos de antes (comparação byte a byte);
- runtime publicado é o **mesmo objeto** (identidade, não igualdade);
- adapter candidato fechado;
- categoria de erro correta, sem `applied`;
- `__cause__` e `__context__` nulos.

**Falhas DEPOIS de `os.replace`** — `fsync` do diretório. Nenhuma asserção de
bytes antigos se aplica aqui, e a suíte **não** as exige:
- o arquivo em disco é o **novo**, completo e válido;
- o runtime publicado é o **novo** (§7.6);
- resposta `CONFIG_DURABILITY_ERROR`, HTTP `500`, `applied: true`,
  `current_revision` = a nova;
- nada da mensagem original aparece em resposta ou registro;
- uma retentativa cega em seguida recebe `409 REVISION_CONFLICT` e não
  sobrescreve nada.

### 12.5 Filesystem, crash e durabilidade
- **`fsync` do temporário e `fsync` do diretório testados separadamente**, com
  falhas independentes e desfechos diferentes (§12.4).
- No Windows, o passo de `fsync` de diretório é **omitido** e o teste afirma a
  omissão — não a simula como sucesso.
- Exceção injetada **entre** `replace` e swap: o arquivo em disco é o documento
  novo, completo; um `build_application` novo sobre ele sobe com a revision
  nova.
- Leitor concorrente durante a escrita vê o documento antigo ou o novo, nunca
  metade.
- Temporário órfão que casa o padrão exato é removido no startup; arquivo de
  terceiro com outro nome `.tmp` no mesmo diretório **não** é tocado.
- Startup recusa: `masking.yaml` symlink; não-regular; gravável por
  grupo/outros; diretório pai gravável por grupo/outros.
- Temporário e backup criados com `O_EXCL` e `0600` — verificado por `stat`,
  não por intenção.
- **`CONFIG_OUT_OF_SYNC`, primeira verificação:** arquivo alterado por fora
  entre o boot e a escrita → `409`, arquivo **não** sobrescrito, runtime
  intacto.
- **`CONFIG_OUT_OF_SYNC`, segunda verificação — a corrida real:** o arquivo é
  alterado **depois** da primeira verificação e **antes** do `os.replace`, por
  injeção no ponto entre validação/conexão e persistência. Esperado: `409
  CONFIG_OUT_OF_SYNC`, conteúdo do editor **preservado**, temporário removido,
  candidato fechado, runtime publicado inalterado (§7.5.1).
- **Arquivo de lock:** `masking.yaml.lock` como symlink → startup recusado;
  como não-regular → recusado; com modo mais permissivo que `0600` → recusado.
  Criado com `O_EXCL` e `0600` quando ausente — verificado por `stat`. Ao
  reutilizar um existente, tipo e permissões são checados **antes** da
  abertura. O descritor permanece aberto enquanto o processo vive (verificado
  por inspeção dos fds abertos).

### 12.6 Leakage
- Token, chave HMAC e DSN não aparecem em nenhum corpo, header, registro de
  auditoria ou mensagem de erro — inclusive nos caminhos de erro.
- `repr` da app, do registry e do runtime não contêm secret.
- Nenhuma resposta de erro carrega `str(exc)`, traceback ou cadeia de exceção.
- Uma sessão MCP não vê byte estranho em `stdout` com o admin ativo.

### 12.7 Bypass e superfície HTTP
- O conjunto de rotas registradas é **igual** à lista de §1. Rota nova quebra o
  teste.
- `/query`, `/sql`, `/execute`, `/config:reload`, `/docs`, `/openapi.json`,
  `/redoc` → `404`.
- Sem token → `401`; token errado → `401`; token em query string → `401`.
- `401` chega **antes** de qualquer `422`: sem token não se sonda o schema.
- `Origin` presente → `403`; `Host` alheio → `400`.
- **`Content-Type` só é exigido em método com corpo:** `GET` sem
  `Content-Type` → `200`; `POST`/`PUT`/`DELETE` com corpo e
  `Content-Type: text/plain` → `415`.
- **Limite de 1 MiB cobre corpo streaming/chunked:** requisição sem
  `Content-Length`, enviada em chunks, é cortada em 1 MiB com `413` — sem
  bufferizar o corpo inteiro antes de decidir. Testado com corpo chunked de
  vários MiB, verificando também que a memória do processo não acompanha o
  envio.
- **`Cache-Control: no-store` em toda resposta administrativa**, inclusive nas
  de erro e nas de `401`.
- **Nenhum header CORS em nenhuma resposta**, inclusive erros.
- **Sem redirect implícito:** `/admin/v1/rules/` não redireciona para
  `/admin/v1/rules`; `redirect_slashes` desligado; path desconhecido → `404`,
  nunca `307`.
- **`HEAD`** numa rota `GET`: exige autenticação, devolve o mesmo status e
  corpo vazio.
- **`OPTIONS`** em qualquer rota: não registrado, sem header CORS.
- Toda tentativa de alterar proteção estrutural → `IMMUTABLE_FIELD` ou rota
  inexistente.
- **`allowed_pg_functions` no corpo de `PUT /sql` ou `PUT /config` →
  `IMMUTABLE_FIELD`.**
- **Ausente → valor preservado semanticamente:** depois de um `PUT /config` que
  altere outras seções, o valor validado de `allowed_pg_functions` é **igual em
  conteúdo e em ordem** ao de antes. A comparação é **modelo validado contra
  modelo validado** — nunca fatia de texto contra fatia de texto, porque a
  reserialização do YAML pode mudar aspas, indentação e ordem de chaves sem
  mudar o valor (§11.3).

### 12.8 Separação de planos
- Teste de AST no estilo de `test_purity.py`: nenhum módulo de `admin/` importa
  `maskgw.mcp`; nenhum de `mcp/` importa `maskgw.admin`; **só `bootstrap/`
  importa os dois**.
- `runtime/` não importa `admin/`, `mcp/` nem `gateway/`.
- `admin/` não importa `logging` (extensão do teste global existente).
- `masking/` continua puro: importar `maskgw.masking` não carrega `admin/`,
  FastAPI nem psycopg.

### 12.9 Migração
- O `config/masking.yaml` atual, sem `id` e sem `revision`, carrega; o MCP sobe.
- Escrita antes da adoção → `409 CONFIG_NOT_ADOPTED`.
- **Caminho A — adotar quando cabe:** estado não adotado e
  `expected_revision: 0` → `200`; `revision` passa de `0` para `1`; todo item
  ganha `id`; `adopted: true` no `GET` seguinte.
- **Caminho B — recusar quando já adotada:** segunda chamada →
  `409 CONFIG_ALREADY_ADOPTED`; bytes do arquivo **idênticos**; **nenhum novo
  backup criado**; **os IDs são os mesmos** de antes (não foram regerados);
  revision inalterada.
- `config:adopt` com `expected_revision != 0` → `409 REVISION_CONFLICT`.
- Escrita não-adoção com estado não adotado → `409 CONFIG_NOT_ADOPTED`.
- Adoção sem `confirm_comment_loss` → recusada.
- **O backup contém os bytes originais exatos** (comparação byte a byte com uma
  cópia feita antes), tem modo `0600` e foi criado com `O_EXCL`.
- **Backup existente nunca é sobrescrito:** com o nome já ocupado, a adoção
  falha com `CONFIG_WRITE_ERROR` e o `masking.yaml` fica intacto.
- **A adoção não altera nenhuma decisão de masking**: veredito do engine
  idêntico, antes e depois, sobre uma tabela de nomes de coluna cobrindo regra,
  exception, alias e coluna sem correspondência.
- Adoção é idempotente na segunda chamada: recusada, não repetida.

### 12.10 Startup e shutdown
- Bind ocupado → o processo **não sobe**, e o MCP nunca fica disponível.
- Bind fora de loopback em `MASKGW_ADMIN_BIND` → recusa no startup.
- Token ausente ou com menos de 32 caracteres, com admin habilitado → recusa.
- `MASKGW_ADMIN_ENABLED` ausente → nenhuma porta aberta, nenhuma thread nova,
  comportamento idêntico ao de hoje.
- Shutdown: thread HTTP com `join`, runtimes fechados depois dela, lock de
  arquivo liberado, **nenhuma thread viva** ao final (verificado por
  `threading.enumerate`).

### 12.11 `config:validate`
- Sem token → `401`.
- Documento com schema válido e `regex` de padrão inválido → recusado: prova
  que **compila**, não só valida schema.
- Transformer inexistente e parâmetro ausente → recusados.
- **Não altera revision**, não escreve arquivo (bytes idênticos), não cria
  adapter (contador de conexões inalterado), não aparece na auditoria como
  escrita.
- `expected_revision` no corpo → `422`.

---

## 13. Escopo de auditoria

### 13.1 O limite atual, declarado

`audit/` emite metadata estruturada via `logging` e **não tem armazenamento
consultável**. Não existe histórico para responder.

Consequência: **a Fase 7 não terá `GET /admin/v1/audit/*`.** Um endpoint desses
exigiria um store com retenção, rotação e modelo de acesso próprio — uma fase
inteira. Inventá-la aqui entregaria um endpoint que mente.

### 13.2 `AdminAudit` — schema fechado

Fechado por construção, como `QueryAudit`. Sem `**kwargs`, sem dicionário
livre, sem campo de texto aberto.

| campo | tipo | conteúdo |
|---|---|---|
| `request_id` | `str` | correlação, gerado pelo servidor |
| `operation` | `str` | enum fechado: `adopt`, `validate`, `config_put`, `rule_create`, `rule_update`, `rule_delete`, `rules_reorder`, `exception_create`, `exception_update`, `exception_delete`, `database_put`, `sql_put` |
| `target_kind` | `str \| None` | enum fechado: `rule`, `exception`, `config`, `database`, `sql` |
| `target_id` | `str \| None` | o **ID administrativo** do item (`rul_…`, `exc_…`), quando a operação tem alvo único |
| `outcome` | `str` | enum fechado: `success`, `rejected`, `error` |
| `revision_before` | `int \| None` | |
| `revision_after` | `int \| None` | ausente quando nada foi publicado |
| `duration_ms` | `int` | |
| `error_category` | `str \| None` | uma das categorias de §10.2 |

`target_id` estava descrito em texto na versão anterior e faltava no schema.
Está no schema.

### 13.3 O que nunca entra no registro

**`match`, nomes de coluna, `config` de transformer, corpo da requisição,
token, qualquer secret, mensagem de erro original.**

A exclusão do `match` é consistência com D-035 e `docs/SECURITY.md`: nomes de
coluna não são registrados porque um nome pode ser revelador — e o `match` de
uma regra **é** um nome de coluna. Registra-se o `target_id` e a operação, que
é o que permite correlacionar sem revelar.

### 13.4 Contadores em memória

`GET /admin/v1/status` expõe contadores desde o start — revision atual,
runtimes aposentados abertos, contagem de queries e de operações
administrativas. **São contadores, não histórico**, e se perdem no restart. O
schema do status diz isso.

Um store de auditoria consultável entra em `docs/FUTURE-HARDENING.md` como
proposta com custo, não como pendência da Fase 7.

---

## 14. Decisões aprovadas e confirmações

### 14.1 As quatro questões, decididas

| # | questão | decisão |
|---|---|---|
| 1 | `allowed_pg_functions` | **somente leitura** na Admin API; `PUT /sql` e `PUT /config` não o acrescentam, removem nem alteram; a lista "nunca-liberável" foi **removida** da Fase 7; o loader **não muda** nesta fase, e seu hardening é proposta separada (§11.3) |
| 2 | runtimes aposentados | **limite 1**; com um aposentado em uso, novo reload → `409 RELOAD_BUSY`, verificado **antes** de construir e conectar; teto de 2 conexões simultâneas, com teste (§8.5) |
| 3 | porta default | **8765**, aprovada (§3.1) |
| 4 | comentários do YAML | perda **aceita** após `confirm_comment_loss: true`, com backup dos bytes originais exatos, criação exclusiva, `0600`, `fsync`, nunca sobrescrito; os comentários passam a viver no backup e na documentação (§5.4) |

### 14.2 Confirmado, sem ambiguidade

| item | confirmação |
|---|---|
| execução de SQL pela Admin API | **não existe** — D-049, verificado por enumeração de rotas |
| front-end | **não** — é a Fase 8, e depende desta |
| deployment | **não** — sem TLS, sem proxy reverso, sem systemd, sem Docker; é a Fase 9 |
| bind fora de loopback | **não** — recusado no startup; pertence à Fase 9 (§3.1) |
| HTTP MCP | **não** — MCP continua stdio only (D-036) |
| `config:reload` | **não existe** na primeira versão (§1.4) |
| MCP altera configuração | **não** — não há, e não haverá, superfície MCP para isso |
| handler ou schema compartilhado entre os planos | **não** — só o bootstrap conhece os dois (§9) |
| DSN como campo administrativo | **não** — só secret/env, nem para leitura |
| `enabled` por regra | **não** nesta versão (D-053) |
| configuração administrável em NFS/SMB | **não suportada** — condição declarada, sem detecção automática (§7.1) |
| validação de ACL no Windows | **não realizada, e não prometida** — verificação de permissão é best-effort ali (§7.1) |
| teto de tempo para o runtime aposentado | **não existe** — ele vive até a query liberar a referência; `RELOAD_BUSY` pode persistir (§8.5) |
| exclusão mútua contra editor não cooperante | **não garantida** — há detecção em duas verificações, e uma janela final que nenhuma técnica portátil fecha (§7.5.2) |
| FastAPI no `pyproject.toml` | **só quando esta especificação for aprovada** |

---

## 15. Ordem de implementação proposta

Cada etapa termina com suíte verde, `ruff` e `mypy --strict` limpos. Nenhuma
começa antes de a anterior fechar.

| # | etapa | fecha |
|---|---|---|
| 1 | `revision` e `id` opcionais nos modelos; compatibilidade do arquivo atual | §5.2, §12.9 |
| 2 | `runtime/`: registry imutável, refcount, `retired`, fechamento único, limite 1 | §8, §12.3 |
| 3 | Gateway adquire/libera runtime por query | §8.2, §12.2 |
| 4 | `bootstrap/`: composition root, startup e shutdown, sem admin ainda | §9, §12.8, §12.10 |
| 5 | Filesystem: verificações, lock de arquivo, escrita atômica, digest, limpeza de temporários | §7.1–7.3, §7.5, §12.5 |
| 6 | Seção crítica administrativa e o fluxo de §7.4 fim a fim, incluindo §7.6 | §6, §7.4, §7.6, §12.1, §12.4 |
| 7 | App HTTP: auth, bind, anti-CSRF, headers, limites, handlers de erro, rotas de leitura | §2, §3, §4, §10, §12.7 |
| 8 | `config:validate` | §1.2, §12.11 |
| 9 | Rotas de escrita e adoção com backup | §1.3, §5.3, §5.4, §12.9 |
| 10 | `AdminAudit` em `audit/` | §13 |
| 11 | Suíte adversarial administrativa | §12.6, §12.7, §12.8 |

Se qualquer etapa revelar que uma decisão aqui está errada, ela volta para
aprovação antes de o código seguir. Não se avança de fase com teste falhando,
nem sem aprovação.
