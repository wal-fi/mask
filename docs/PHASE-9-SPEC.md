# Fase 9 — PostgreSQL Gateway, múltiplos datasources e Admin UX v2

**Estado:** especificação aprovada em 2026-09-22; Etapa 1 documental concluída.
**Base:** Fase 8 concluída em `42cd2df8aeef4a1e39ffae0ecf33a6ce86bd8445`.
**Implementação funcional:** não iniciada.

Esta aprovação é documental. As Etapas 2–12 continuam bloqueadas para
implementação até revisão e autorização próprias, na ordem desta especificação.
Nenhum módulo, modelo, rota, dependência, listener ou recurso descrito abaixo
existe no produto atual.

## 1. Motivo e resultado esperado

O produto atual é um servidor MCP `stdio` que se conecta como cliente a um
único PostgreSQL. Uma IDE não consegue usar o Gateway como host PostgreSQL. O
DSN vem de `MASKGW_DATABASE_DSN`, e o runtime administrativo gerencia somente
essa conexão e sua política.

A Fase 9 acrescenta um segundo plano de dados, sem remover o MCP:

```text
IDE / psql ── PostgreSQL protocol ──► PGWire Gateway ──► Gateway seguro
Claude/IA ───────── MCP stdio ──────► Gateway seguro ──► PostgreSQL
Admin UI ─────────── HTTP(S) ───────► catálogo de datasources e políticas
```

O aceite principal é uma IDE poder configurar somente:

```text
host     = endereço do Gateway
port     = porta PostgreSQL do Gateway
dbname   = alias administrativo do datasource
user     = usuário do Gateway
password = senha do Gateway
```

e então navegar metadados e executar consultas `SELECT`, recebendo resultados
mascarados. A IDE nunca recebe a credencial do PostgreSQL de destino e nunca
se conecta diretamente a ele.

## 2. Princípios que não mudam

- O cliente MCP, a IDE e qualquer usuário SQL são não confiáveis.
- Dados originais nunca atravessam uma fronteira de saída sem decisão do
  Masking Engine.
- Somente leitura. Escritas, DDL, `COPY`, execução arbitrária e funções
  perigosas continuam recusadas.
- O PostgreSQL de destino também força sessão read-only e
  `statement_timeout`; o parser não é a única defesa.
- Erros, logs, auditoria e métricas nunca carregam SQL, valores, senhas, DSN,
  ciphertext, chaves ou resultados.
- Segurança > correção > compatibilidade > desempenho > conveniência.
- MCP e PGWire reutilizam o mesmo pipeline seguro; nenhum deles chama o
  adapter bruto.
- A Admin API não executa SQL de usuário. “Testar conexão” realiza somente o
  handshake e os capability checks fechados do produto.
- A Administração v2 permanece local e loopback-only nesta fase. O bind externo
  do plano administrativo não é implícito no bind PGWire e não é parte da
  aprovação.

## 3. Escopo

### 3.1. Incluído

- listener compatível com PostgreSQL Frontend/Backend Protocol 3.0;
- bind e porta próprios, desligados por default;
- TLS obrigatório fora de loopback;
- autenticação do Gateway separada da autenticação upstream;
- alias de `dbname` resolvido para um datasource cadastrado;
- múltiplos datasources PostgreSQL;
- credencial técnica read-only por datasource;
- armazenamento persistente autenticado e criptografado dos segredos;
- política de masking e limites por datasource;
- seleção explícita de datasource pelo plano PGWire;
- datasource default e seleção opcional por alias no MCP;
- CRUD e teste de conexão de datasource pela Admin API/UI;
- redesign completo da apresentação administrativa, preservando os controles
  de segurança e a ausência de execução SQL na UI;
- compatibilidade certificada inicialmente com `psql`, DBeaver, DataGrip e
  pgAdmin;
- testes de protocolo, integração, concorrência, segurança e pacote instalado.

### 3.2. Fora do escopo

- MySQL, SQL Server, Oracle ou protocolo genérico;
- escrita SQL, DDL, migrations de bancos de negócio ou funções de DBA;
- RBAC complexo, SSO, OAuth, LDAP, Kerberos, GSSAPI ou identidade federada;
- pass-through da senha do PostgreSQL fornecida pela IDE;
- pooling transacional que compartilhe estado entre sessões de clientes;
- `COPY`, replicação, `LISTEN`/`NOTIFY` e large objects;
- compatibilidade prometida com toda ferramenta sem certificação;
- editor SQL, resultados de consultas ou auditoria consultável na Admin UI;
- descoberta automática de servidores na rede;
- segredo em browser, YAML em claro, argumento de processo, log ou resposta;
- mascaramento profundo arbitrário de JSON, XML, arrays ou blobs.

## 4. Modelo de conexão

### 4.1. Alias como `dbname`

O campo `database` do `StartupMessage` é um alias estável e único cadastrado no
Gateway, por exemplo `crm-producao`. Ele não precisa ser igual ao database real.

- 1 a 63 caracteres;
- ASCII minúsculo, dígitos, `_` e `-`;
- primeiro caractere alfanumérico;
- comparação exata após validação;
- aliases reservados do Gateway recusados;
- rename não suportado no MVP: criar novo alias e remover o anterior evita
  sessões apontando silenciosamente para outro destino.

Alias ausente, desabilitado ou desconhecido falha antes de abrir conexão
upstream e retorna erro PostgreSQL sanitizado.

### 4.2. Credenciais em duas fronteiras

Existem dois segredos diferentes:

1. **credencial do Gateway**, digitada na IDE e validada pelo listener;
2. **credencial upstream**, cadastrada administrativamente e usada pelo
   Gateway para conectar ao PostgreSQL real.

Não há relay transparente. O Gateway termina autenticação e inicia uma nova
conexão autenticada ao destino. Um proof SCRAM recebido do cliente não vira
senha reutilizável contra outro servidor, salt e nonce.

O MVP usa um único principal operacional do Gateway, configurado fora do
estado administrativo. O método normativo de autenticação do MVP é
**SCRAM-SHA-256**; não há fallback para MD5, senha em claro ou relay de um
proof recebido para o upstream:

- `MASKGW_PGWIRE_USERNAME`;
- `MASKGW_PGWIRE_PASSWORD`;
- acesso a todos os aliases habilitados;
- sem matriz de permissões por usuário nesta fase.

A senha do Gateway só existe na fonte de segredo e na memória necessária para
autenticação; não é persistida no catálogo, não aparece na UI e não é enviada
ao PostgreSQL upstream. Falhas de usuário, senha ou alias usam a mesma resposta
externa sanitizada e não enumeram o catálogo. Limites de tentativas e custo
uniforme de falha são gate da Etapa 7; a rede de implantação pode acrescentar
rate limiting, mas não é uma dependência do protocolo.

Essa limitação deve aparecer claramente na UI e na documentação. Usuários,
grupos ou autorização por datasource exigem fase própria.

### 4.3. Credencial upstream

Cada datasource possui uma credencial técnica distinta, com no mínimo:

- `CONNECT` no database real;
- `USAGE` nos schemas permitidos;
- `SELECT` nos objetos permitidos;
- sem ownership, criação, escrita, execução de funções de usuário ou bypass de
  RLS;
- `default_transaction_read_only=on` e timeout impostos e verificados em toda
  conexão.

A UI aceita a senha somente em criação ou rotação. Leituras posteriores
devolvem apenas `configured: true|false`; nunca valor, tamanho, hash, nonce ou
ciphertext.

## 5. Listener PostgreSQL

### 5.1. Ativação e settings aprovados

| variável | default | regra |
|---|---|---|
| `MASKGW_PGWIRE_ENABLED` | desligado | somente `1` bruto habilita |
| `MASKGW_PGWIRE_BIND` | `127.0.0.1` | externo exige TLS |
| `MASKGW_PGWIRE_PORT` | `6432` | 1..65535 |
| `MASKGW_PGWIRE_USERNAME` | ausente | obrigatório quando habilitado |
| `MASKGW_PGWIRE_PASSWORD` | ausente | segredo obrigatório no MVP |
| `MASKGW_PGWIRE_TLS_CERT` | ausente | obrigatório fora de loopback |
| `MASKGW_PGWIRE_TLS_KEY` | ausente | obrigatório fora de loopback |
| `MASKGW_PGWIRE_MAX_SESSIONS` | `32` | limite global positivo |
| `MASKGW_PGWIRE_IDLE_TIMEOUT_MS` | `300000` | encerra sessão ociosa |
| `MASKGW_DATASOURCE_MASTER_KEY` | ausente | obrigatório para estado persistente |
| `MASKGW_DATASOURCE_STORE` | `config/datasources.store` | arquivo regular local seguro, resolvido ao lado da configuração |

Como nas flags existentes, não há interpretação permissiva de booleano.
O catálogo novo só é aberto quando `MASKGW_PGWIRE_ENABLED=1`; com a nova
capacidade desligada, store e chave-mestra não são carregados e o modo legado
continua disponível. Setting inválido falha antes de bind e antes de
disponibilizar MCP.

### 5.2. TLS

- Bind não-loopback sem certificado e chave válidos é recusado no startup.
- Para decidir se um bind é loopback, somente os literais IP `127.0.0.1` e
  `::1` contam como loopback; um hostname é tratado como externo para a
  exigência de TLS, mesmo que atualmente resolva para loopback.
- Chave privada deve ser arquivo regular, não symlink e com permissões seguras.
- A senha nunca trafega fora de TLS quando o peer não é loopback.
- `SSLRequest` deve ser suportado; downgrade é recusado quando TLS é obrigatório.
- Em bind externo, `StartupMessage` sem TLS é recusado; responder `N` ao
  `SSLRequest` não é permitido. Em loopback, TLS continua opcional e um
  `SSLRequest` só recebe `S` quando um contexto TLS válido foi configurado.
- Versão mínima TLS 1.2; TLS 1.3 preferida quando disponível.
- Certificados não são gerados automaticamente pelo produto.
- Proxy Protocol, `X-Forwarded-*` e terminação TLS implícita ficam fora.

### 5.3. Compatibilidade obrigatória

O listener implementa e testa:

- `SSLRequest` e startup protocol 3.0;
- `StartupMessage` com `user`, `database` e `application_name` limitado;
- autenticação SCRAM-SHA-256, sem método alternativo no MVP;
- `ParameterStatus`, `BackendKeyData` sintético e `ReadyForQuery`;
- simple query;
- extended query: `Parse`, `Bind`, `Describe`, `Execute`, `Close` e `Sync`;
- parâmetros posicionais e prepared statements por sessão;
- `Flush`, `Terminate` e recuperação após erro até `Sync`;
- `CancelRequest` autenticado pelo par PID/chave sintéticos;
- `RowDescription`, `DataRow`, `CommandComplete`, `EmptyQueryResponse` e erros
  sanitizados;
- formatos textuais necessários aos clientes certificados.

Mensagem, protocolo ou formato não suportado é recusado deterministicamente,
sem queda de processo e sem encaminhamento cego.

### 5.4. Semântica SQL para IDEs

O comando de usuário continua sendo `SELECT` único. Para uma IDE iniciar e
navegar, o listener também precisa de um conjunto mínimo, fechado e testado de
operações de sessão e metadados:

- respostas locais a parâmetros controlados pelo Gateway;
- `SHOW` seguro quando puder ser respondido sem upstream arbitrário;
- transações somente leitura delimitadas, se necessárias;
- consultas de `information_schema` e `pg_catalog` exigidas pelos clientes;
- funções de catálogo individualmente permitidas, nunca prefixo inteiro.

Não existe exceção genérica “consulta da IDE”. Cada statement e função entram
em catálogo versionado, com contraprova de escrita, leitura de arquivo,
execução de função de usuário, introspecção de segredo e bypass do masking.

### 5.5. Metadados e tipos

- Proveniência real continua interna.
- O listener não expõe OID de tabela ou atributo quando revelar mecanismo;
  pode emitir zero nesses campos.
- Coluna não mascarada preserva tipo quando a codificação for garantida.
- Coluna mascarada é anunciada como texto, pois transformer pode alterar tipo.
- `NULL` permanece `NULL`.
- Formato binário nunca pode contornar masking; enquanto não suportado, falha
  antes da execução.
- Nomes duplicados continuam válidos e posicionais.
- Como `max_rows` não possui campo nativo, truncamento devolve as linhas
  permitidas e um `NOTICE` fixo; o contrato exato será fechado antes do código.

Consultas de metadados da IDE não são uma exceção genérica: são templates
locais versionados por cliente e datasource, com operações e funções
individualmente permitidas. SQL arbitrário contra `information_schema` ou
`pg_catalog` continua passando pelo mesmo validator e pelas mesmas recusas.

## 6. Catálogo de datasources

### 6.1. Modelo administrativo

Cada datasource possui:

- ID opaco estável escolhido pelo servidor;
- alias público usado como `dbname`;
- nome de apresentação e estado `enabled`;
- host, porta, database e usuário upstream;
- senha upstream cifrada e opções TLS fechadas;
- política de masking, limites e política SQL;
- revision própria;
- status sanitizado do último teste;
- timestamps operacionais não sensíveis.

`enabled=false` impede novas sessões PGWire, novas consultas MCP por esse alias
e novos testes de conexão. Sessões já admitidas mantêm a geração que capturaram
e drenam até o limite de sessão; não mudam silenciosamente de destino. Remoção
usa a mesma drenagem, depois da qual o alias deixa de existir. O detalhe de
estado `active`/`draining` é interno e não é exposto ao cliente SQL.

Host, database e usuário são privados. Não aparecem para clientes PGWire ou
MCP, em logs ou erros externos.

### 6.2. Persistência e criptografia

A decisão aprovada é um documento versionado gerido por máquina, com escrita
atômica já comprovada, catálogo autenticado e campos secretos cifrados
individualmente por **AES-256-GCM**. A Etapa 2 deverá escolher uma biblioteca
madura e fixar o envelope binário/JSON versionado antes de escrever código; isso
é detalhe de implementação, não autorização para criptografia própria.

Requisitos independentes do formato:

- chave-mestra somente por secret provider/ambiente;
- chave de 256 bits em representação canônica (32 bytes, codificados como 64
  dígitos hexadecimais ASCII);
- AES-256-GCM de biblioteca madura;
- nonce único de CSPRNG por cifragem;
- Associated Data liga ciphertext a datasource, campo, versão e revision do
  catálogo;
- nenhuma chave derivada de senha humana;
- alteração de ciphertext falha fechada;
- o documento inteiro, inclusive alias, destino, policy e ciphertexts, tem uma
  autenticação canônica separada; alterar metadata sem tocar em um segredo
  também falha fechado;
- transplantar ciphertext entre datasource/campo ou revision falha fechado;
- leitura nunca devolve segredo;
- rotação explícita, sem fallback silencioso;
- arquivo, diretório, lock, temporários, permissões, `fsync`, digest e rename
  seguem ou fortalecem D-048 a D-050;
- backup nunca contém plaintext.

Replay de um arquivo inteiro é diferente de transplantar um campo. Um arquivo
substituível não consegue detectar sozinho que uma versão autenticada antiga foi
restaurada. Portanto a Etapa 2 deve fornecer e testar uma âncora monotônica
confiável, fora do conteúdo substituível do catálogo, ou registrar uma decisão
de ameaça equivalente antes de implementar. Sem essa âncora, startup fail-closed
é obrigatório e a Etapa 2 não pode declarar replay de arquivo fechado.

Não implementar criptografia própria.

### 6.3. Migração do modo único

`MASKGW_DATABASE_DSN` continua funcionando no modo legado enquanto PGWire e o
catálogo multi-datasource estiverem desligados. A adoção é explícita:

1. administrador habilita o store;
2. UI oferece importar o datasource legado;
3. senha é cifrada e política copiada;
4. candidato conecta e passa capability checks;
5. estado é persistido e runtime publicado;
6. somente depois o alias fica disponível.

Não apagar nem reescrever automaticamente `masking.yaml`. Rollback desliga a
nova capacidade e volta ao modo anterior após restart. Se o catálogo novo
estiver habilitado e inválido, não há fallback silencioso para o DSN legado:
todas as fronteiras permanecem indisponíveis. Só o desligamento explícito da
capacidade, seguido de restart, seleciona o modo legado.

## 7. Runtime multi-datasource

```text
DatasourceRegistry
├── crm-producao  → generation 12 → policy/runtime
├── financeiro    → generation 4  → policy/runtime
└── homologacao   → generation 9  → policy/runtime
```

Requisitos:

- acquire/release por alias e generation;
- swap de um datasource não bloqueia queries nos demais além da seção mínima;
- runtime aposentado fecha uma vez após refcount zero;
- remoção impede novas sessões e deixa sessões admitidas terminar sob limite;
- limites de candidatos/aposentados por datasource e globais;
- teste de conexão não publica runtime;
- criação/rotação testa candidato antes de persistir e publicar;
- falha em um datasource não corrompe os demais;
- startup integralmente fail-closed para datasource habilitado inválido, salvo
  decisão futura baseada em evidência.

Cada sessão PGWire mantém conexão upstream própria no MVP, preservando estado
de prepared statements e transação sem pooling transacional. Limites global e
por datasource impedem exaustão.

## 8. Admin API v2

Novas capacidades sob `/admin/v2`, sem alterar silenciosamente v1:

- listar e ler datasources sem secrets;
- criar e editar datasource;
- rotacionar credencial;
- testar candidato sem publicar;
- habilitar/desabilitar e remover com confirmação;
- ler e editar policy por datasource;
- definir datasource default do MCP;
- status agregado e por datasource;
- revision e concorrência otimista em toda escrita.

Mutações usam corpo fechado, limite, autenticação, anti-CSRF, auditoria após a
seção crítica e erros sanitizados. Nenhuma rota recebe ou devolve DSN pronto:
host, porta, database, usuário e senha são campos distintos e validados.

O token administrativo atual pode permanecer na primeira entrega. Bind externo
da Admin API não é autorizado automaticamente pelo bind PGWire; exige decisão
separada com TLS.

Essa separação é normativa: `/admin/v2` continua usando a fronteira local da
Admin API, sem CORS, bind externo ou exposição automática por habilitar PGWire.

## 9. Admin UX v2

O redesign não é somente troca de cores. Deve reduzir carga cognitiva e tornar
fluxos operacionais evidentes sem enfraquecer a Fase 8.

### 9.1. Estrutura

- sidebar persistente e cabeçalho compacto;
- dashboard com estado, listeners e resumo de datasources;
- página de datasources com busca, estado e última verificação;
- wizard: identificação, destino, credencial, TLS, policy, teste e revisão;
- detalhe com Visão geral, Conexão, Masking, Limites e SQL;
- editor de regras em linguagem humana, com ordem visível;
- estados vazios, loading, sucesso, conflito e erro acionáveis;
- confirmação destrutiva pelo alias;
- temas claro/escuro e layout responsivo;
- nenhuma visualização de senha após envio;
- nenhum editor SQL ou grid de resultados.

### 9.2. Qualidade e acessibilidade

- tokens de design para espaço, tipografia, cor, raio e elevação;
- contraste WCAG AA, foco visível e tabulação previsível;
- uso integral por teclado, inclusive reorder;
- labels, descrições e erros ligados aos campos;
- status nunca comunicado só por cor;
- 320 CSS px, zoom de 200% e `prefers-reduced-motion`;
- sem fonte, ícone, analytics ou recurso externo;
- screenshots de referência aprovados antes das mutações novas.

### 9.3. Arquitetura frontend

Preservar inicialmente pacote embarcado, mesma origem local, CSP, ausência de CORS,
token em memória e rendering sem HTML arbitrário. A apresentação declarativa
pode ser estendida se continuar tipada e testável. Framework ou remoção da
divisão público/privado de D-062 exige decisão, análise de risco e nova revisão.

## 10. MCP multi-datasource

A tool continua única e somente leitura:

```text
query_database(sql: str, database: str | None = None)
```

- `database=None` usa o alias default;
- alias explícito seleciona somente datasource habilitado;
- nenhuma tool lista credencial, altera datasource ou configuração;
- cliente não informa host, porta, usuário, senha, transformer ou limites;
- erro de alias é fixo e não enumera aliases;
- clientes que enviam somente `sql` continuam funcionando.

O contrato atual continua `query_database(sql: str)` até a Etapa 11. A extensão
opcional `database` só será publicada nessa etapa, depois do registry e do
rollback legado estarem implementados e testados. O MCP permanece `stdio`; esta
fase não adiciona MCP HTTP.

## 11. Lifecycle

Startup normativo:

1. validar flags e settings de todas as fronteiras, sem abrir store novo quando
   PGWire estiver desligado;
2. validar recursos UI;
3. validar store, lock e chave-mestra;
4. carregar e autenticar catálogo;
5. compilar policies;
6. verificar datasources habilitados;
7. construir registry multi-datasource;
8. iniciar e confirmar Admin HTTP local;
9. iniciar e confirmar PGWire quando habilitado;
10. somente então disponibilizar MCP.

Shutdown interrompe primeiro a admissão nas duas fronteiras, aguarda/cancela
trabalho sob limites, drena sessões PGWire por geração, fecha sessões upstream,
runtimes e stores. Nenhuma thread ou socket fica abandonado. Não há retry,
rebind ou rollback automático em nenhuma falha de lifecycle.

## 12. Ameaças novas

Cobertura obrigatória:

- brute force, enumeração de usuário/alias e timing;
- downgrade TLS e certificado inválido;
- StartupMessage enorme, duplicado, malformado ou com UTF-8 inválido;
- framing com tamanho negativo, overflow, truncamento e mensagem fora de estado;
- desync entre simple e extended protocol;
- prepared statement alterado entre `Parse` e `Bind`;
- parâmetros tentando reintroduzir SQL;
- formatos binários e tipos malformados;
- cancelamento cruzado entre sessões;
- exaustão de conexões, sockets lentos e sessão ociosa;
- catálogo tentando ler funções, arquivos, secrets ou configuração;
- alias trocado por corrida administrativa;
- remoção/rotação com sessões em voo;
- ciphertext transplantado entre datasource/campo;
- perda, troca e rotação incompleta da chave-mestra;
- SSRF, DNS rebinding, loopback, link-local e metadata cloud upstream;
- leakage em erro, `NOTICE`, auditoria, logs e UI;
- regressões de F-01 a F-11 e dos riscos aceitos.

A política recomendada permite IPs privados e hosts explicitamente autorizados,
e bloqueia loopback, link-local, multicast, metadata cloud e mudança de
resolução, salvo operação local deliberadamente aprovada.

## 13. Observabilidade

Permitido: IDs opacos, contagens, duração em buckets, categoria de erro, bytes
e linhas agregados, estado do listener e generation.

Proibido: SQL, parâmetros, células, resultados, nome sensível, destino real,
usuário upstream, DSN, segredo, ciphertext, nonce, hash, tamanho de segredo,
traceback externo ou mensagem original do PostgreSQL.

## 14. Gates e clientes certificados

### 14.1. Matriz inicial

- `psql` compatível com PostgreSQL 16;
- DBeaver e driver PostgreSQL fixados;
- DataGrip e driver PostgreSQL fixados;
- pgAdmin com runtime fixado;
- psycopg 3 e JDBC em harnesses diretos;
- Claude Code/MCP existente;
- Admin UI em Chromium, Firefox e WebKit.

“Qualquer IDE” significa cliente de protocolo PostgreSQL 3.0 dentro do
subconjunto implementado. A documentação publica a matriz certificada.

### 14.2. Provas mínimas

- conexão por host/port/dbname/user/password;
- TLS externo e recusa de downgrade;
- autenticação certa/errada sem enumeração;
- árvore de schemas/tabelas nos quatro clientes;
- SELECT parametrizado simples e preparado;
- alias, expressão, UNION, CTE e subquery mascarados;
- exception somente pelo nome autoritativo;
- escrita e funções perigosas recusadas;
- cancelamento isolado;
- limites de linhas, timeout, idle e sessões;
- reload de um datasource sem falha nos demais;
- rotação de segredo e chave coerente;
- pacote instalado sem checkout ou Node;
- zero segredo/dado original nos artefatos;
- Python, Node, browsers, Ruff, format, mypy e diff verdes;
- PostgreSQL real, sem skip por DSN ou finding convertido em skip/xfail.

## 15. Etapas aprovadas

| Etapa | Entrega | Gate específico |
|---|---|---|
| 1 | especificação, threat model, decisões e rastreabilidade | baseline; zero código funcional |
| 2 | modelo de datasource, store cifrado e migração | criptografia, atomicidade e leakage |
| 3 | registry multi-datasource e lifecycle | concorrência, refcount e isolamento |
| 4 | Admin API v2 de datasources | auth, CSRF, revisions e teste sem publicação |
| 5 | protótipo e Admin UX v2 somente leitura | screenshots, a11y e três browsers |
| 6 | CRUD visual de datasources e policies | segredo write-only e concorrência |
| 7 | PGWire: startup, TLS e autenticação | harness binário adversarial |
| 8 | simple query e masking | `psql`, psycopg e PostgreSQL real |
| 9 | extended query, parâmetros e cancelamento | JDBC e prepared statements |
| 10 | catálogo e quatro IDEs | navegação real e matriz fixada |
| 11 | MCP multi-datasource e migração legada | clientes antigos e default explícito |
| 12 | pacote, revisão adversarial e fechamento | gates integrais e rollback real |

Cada etapa termina para revisão e autorização próprias. A Etapa 1 foi aprovada
em 2026-09-22; isso não autoriza iniciar a Etapa 2 nem qualquer etapa posterior.
Código funcional só começa dentro da etapa autorizada e após os gates anteriores
estarem verdes.

## 16. Decisões aprovadas em 2026-09-22

1. **PGWire como façade, não proxy transparente:** termina autenticação/TLS,
   interpreta SQL e reconstrói resultados já mascarados.
2. **Alias como database:** `dbname` identifica datasource; destino real nunca
   vem do cliente.
3. **Identidades separadas:** login do Gateway é distinto da credencial técnica
   upstream; sem pass-through.
4. **Autorização simples no MVP:** um principal operacional acessa todos os
   datasources habilitados; RBAC fica fora.
5. **Segredos cifrados:** credenciais upstream somente sob AEAD com chave-mestra
   externa; nunca voltam pela API.
6. **TLS obrigatório fora de loopback:** sem flag de escape.
7. **Conexão upstream por sessão:** sem pooling transacional nesta fase.
8. **Compatibilidade certificada:** `psql`, DBeaver, DataGrip e pgAdmin.
9. **Admin UX v2 preserva a fronteira segura:** mesma origem, assets embarcados,
   token volátil e ausência de SQL/resultados na UI.
10. **MCP compatível:** parâmetro opcional de alias, default explícito e `stdio`.
11. **Modo legado como rollback:** DSN único continua disponível quando a nova
    capacidade está desligada; migração nunca automática.
12. **Fail-closed no startup:** qualquer datasource habilitado inválido impede
    publicação das fronteiras, até decisão posterior baseada em evidência.

As doze decisões acima foram aprovadas integralmente em 2026-09-22 e estão
registradas como D-065 a D-076 em `docs/DECISIONS.md`. O registro documental
não autoriza a implementação: cada etapa 2–12 continua condicionada à sua
própria revisão, aprovação e gates de entrada.

## 17. Critério de conclusão

A Fase 9 só termina quando uma instalação empacotada, sem checkout, permite:

1. cadastrar dois PostgreSQL distintos pela Admin UI;
2. conectar aos dois por aliases usando uma IDE certificada;
3. navegar seus metadados permitidos;
4. executar SELECT simples e preparado;
5. receber masking correto em ambos;
6. provar escrita e bypass bloqueados;
7. consultar os aliases pelo MCP sem regressão;
8. rotacionar uma credencial sem afetar o outro datasource;
9. reiniciar e recuperar estado cifrado sem plaintext residual;
10. desligar a Fase 9 e voltar ao modo legado documentado.
