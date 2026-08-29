# Test Plan

Toda funcionalidade nova deve possuir testes. Nenhuma fase é concluída com
teste falhando. Critérios de aceite por fase estão em `docs/ROADMAP.md`.

## Config Loader (Fase 1)

Deve **impedir a inicialização**:
- YAML malformado
- transformer inexistente
- `mode` inválido
- regex inválida
- parâmetro obrigatório ausente (`value`, `pattern`, `length`)
- regra com `hmac_sha256` sem chave disponível no ambiente
- chave HMAC declarada dentro do `masking.yaml`

Deve carregar com sucesso o `config/masking.yaml` do repositório.

## Matching (Fase 1)

Regra `cpf` deve casar:
- cpf
- CPF
- Cpf
- cPf
- num_cpf
- cod_cpf
- cliente_cpf
- cpf_cliente
- nr_cpf

Modo `exact` deve casar apenas o nome exato, case-insensitive.

Matching com `origin_name = None` usa somente `output_name`.

## Exceptions (Fase 1)

Regra: `cpf → md5`
Exception: `tipo_cpf` (exact)

Esperado:
- cpf → masked
- num_cpf → masked
- tipo_cpf → original

Exception casando por `origin_name` também tem prioridade.

## Default ALLOW (Fase 1)

Coluna que não casa nenhuma regra retorna o valor original.

## Transformers (Fase 1)

Cada transformer deve testar:
- entrada normal
- NULL
- string vazia
- Unicode
- valores grandes
- valores inválidos quando aplicável

Além disso:
- determinismo de md5, sha256, sha512, hmac_sha256, regex, fixed e truncate
- não-determinismo de random
- hmac_sha256 com chaves diferentes produz saídas diferentes

## Database (Fase 2)

Testar:
- SELECT cpf
- SELECT *
- SELECT cpf, email
- JOIN
- UNION
- CTE
- subquery
- view
- NULL vindo do banco

Implementado em duas camadas:

- **sem banco** (`test_db_columns`, `test_db_masking`, `test_db_errors`,
  `test_db_leakage`), com dublês de conexao e cursor — roda em qualquer
  maquina e mantem a suite verde sem PostgreSQL;
- **com PostgreSQL real** (`test_db_integration`), marcado `integration` e
  pulado com SKIP limpo quando `MASKGW_TEST_DSN` nao esta definida.

O DSN vem exclusivamente do ambiente. Nenhum usuario, senha ou host aparece no
codigo ou nos testes.

Alem dos itens acima, a Fase 2 cobre:

- canonicalizacao deterministica por tipo e falha fechada em tipo nao
  suportado (`test_canonical`, D-015)
- preservacao do objeto Python nas colunas sem transformacao
- nomes de coluna duplicados, que nao podem ser colapsados
- leitura em lotes: o resultado nao muda com o tamanho do lote
- estado transacional observado de fora, por `pg_stat_activity` (D-016)
- ausencia de `__cause__` e `__context__` no erro sanitizado (D-017)
- superficie publica de `db/` sem cursor, fetch cru ou acessor de original

### Lacuna da Fase 2, fixada em teste

`SELECT cpf AS documento` passa **em claro**, porque nao ha lineage. Coberto
por `TestPhaseTwoAliasGap`, nas duas camadas. Esses testes serao **invertidos**
na Fase 3.

## Provenance / alias (Fase 3)

- `SELECT cpf AS documento` → masked
- alias em JOIN, subquery, CTE e view → masked
- `SELECT md5(cpf)` → `origin_name is None`, sem erro no pipeline
- teste que mede o que o PostgreSQL devolve em `ftable` por cenário

Implementado em três camadas:

- **medição** (`test_pgresult_metadata`) — não testa código do Gateway. Mede o
  que o PostgreSQL e o psycopg devolvem em `cursor.pgresult.ftable(i)` e
  `ftablecol(i)`, cenário a cenário, e fixa o resultado. Foi escrito **antes**
  da implementação: o resolver segue o que foi medido, não a documentação
  anterior — que estava errada sobre onde esses campos vivem.
- **sem banco** (`test_db_provenance`) — classificação, cache, alinhamento
  posicional e comportamento quando o catálogo falha.
- **com PostgreSQL real** (`test_db_integration`) — os quinze cenários
  obrigatórios ponta a ponta, com a política aplicada.

Ressalva sobre UNION: o PostgreSQL **não** preserva proveniência em UNION
(`ftable = 0`). O critério original do roadmap ("alias em UNION → masked") não
é alcançável por metadata. O teste registra o comportamento real: com o nome
preservado o `output_name` ainda mascara; com alias, passa em claro. Ver
`docs/FUTURE-HARDENING.md`.

### Testes invertidos

`TestPhaseTwoAliasGap`, que na Fase 2 fixava `SELECT cpf AS documento` passando
em claro, virou `TestAliasProtection` nas duas camadas. O valor agora sai
transformado pela regra `cpf`.

## Security (Fase 4)

Verificar bloqueio de:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- TRUNCATE
- CREATE
- GRANT
- REVOKE
- CTE modificadora de dados
- múltiplos statements

Verificar:
- `statement_timeout` interrompe consulta longa
- limite de linhas trunca a resposta e sinaliza truncamento
- escrita que passe pelo validator ainda falha pelo privilégio da role

## Leakage (todas as fases)

Verificar que o valor original não aparece:
- na resposta
- nos logs
- nas exceções
- no stack trace retornado
- na mensagem de erro do PostgreSQL repassada ao cliente

Verificar que a chave HMAC não aparece em log, erro ou resposta.

## Riscos aceitos (Fase 6)

Testes que **documentam o comportamento atual**, para que uma mudança futura
seja percebida:

- `SELECT substr(cpf,1,3) AS x` passa em claro
- coluna sensível com nome fora do padrão passa em claro
- `WHERE cpf LIKE '...'` é permitido
- `ORDER BY cpf` é permitido
- JSONB não é inspecionado internamente

Cada um referencia o item correspondente em `docs/FUTURE-HARDENING.md`.
