# Threat Model

## Atacante

Assumir que o cliente MCP pode tentar obter dados não mascarados.

## Objetivo do atacante

Fazer um dado sensível atravessar o Gateway sem transformação.

## Cenários cobertos pelo MVP

Todos devem resultar em valor mascarado ou em consulta rejeitada.

### Alias
`SELECT cpf AS documento`
Coberto por `origin_name`: o alias muda `output_name`, não a origem.

### SELECT *
`SELECT * FROM cliente`
Coberto: cada coluna expandida tem nome próprio e origem própria.

### JOIN
`SELECT c.cpf FROM clientes c JOIN pedidos p ...`
Coberto por nome e por origem.

### Subquery
`SELECT cpf FROM (SELECT cpf FROM clientes) x`

### CTE
`WITH x AS (SELECT cpf FROM clientes) SELECT cpf FROM x`

### UNION
`SELECT cpf FROM clientes UNION SELECT cpf FROM fornecedores`

### Case manipulation
`CPF`, `Cpf`, `cPf`
Coberto: matching case-insensitive.

### Naming
`cliente_cpf`, `cpf_cliente`, `num_cpf`, `cod_cpf`
Coberto: matching por contains.

### Alias combinado com subquery
`SELECT d FROM (SELECT cpf AS d FROM clientes) x`
Cenário-chave: verificar até onde o PostgreSQL preserva a origem através de
subquery e CTE. Onde a origem se perde, resta o `output_name`.

### Escrita disfarçada de leitura
`WITH x AS (DELETE FROM clientes RETURNING *) SELECT * FROM x`
A raiz é `SelectStmt` mas o statement escreve. O validator precisa inspecionar
CTEs recursivamente, e a role read-only é a segunda barreira.

### Múltiplos statements
`SELECT 1; DROP TABLE clientes`

### Erros
Tentar provocar erros que revelem valores.
Coberto: mensagem do PostgreSQL nunca é repassada.

### Logs
Verificar se valores originais aparecem nos logs.

### Metadata
Verificar se informações sensíveis aparecem por metadata.

### Alteração de regras pelo cliente
Tentar desabilitar masking, injetar exception ou trocar transformer via MCP.
Configuração é imutável em runtime e não há superfície MCP para alterá-la.

## Riscos conhecidos e aceitos no MVP

Documentados, não corrigidos nesta versão. Ver `docs/FUTURE-HARDENING.md`.

### Expressões e funções SQL
`MD5(cpf)`, `LOWER(cpf)`, `CONCAT(cpf)`, `substr(cpf,1,3)`, `cpf::text`

Para expressões o PostgreSQL não informa origem (`table_oid = 0`), então o
matching depende do `output_name`. Alguns casos são pegos — `md5(cpf)` produz
o nome default `md5`, mas `SELECT substr(cpf,1,3) AS x` não casa nenhuma
regra e passa em claro.

Este é o principal bypass residual do MVP. Fica registrado como tal.

### WHERE / ORDER BY como oráculo
```sql
SELECT id FROM clientes WHERE cpf LIKE '123%'
SELECT id FROM clientes ORDER BY cpf LIMIT 1
```
A coluna não aparece no result set, então o Masking Engine não é acionado, mas
o predicado revela informação. Reconstrução por consultas sucessivas é viável.

### Agregações e cardinalidade
`GROUP BY` sobre coluna sensível, ou agregados com poucos registros, permitem
inferência.

### Coluna sensível com nome fora do padrão
Uma coluna `documento`, `doc` ou `ni` contendo CPF não casa nenhuma regra e
passa em claro — consequência direta do default ALLOW.

### Dado sensível dentro de JSONB
Coluna `dados jsonb` contendo `{"cpf": "..."}` não é inspecionada. Se o nome
da coluna casar uma regra, o valor inteiro é transformado; caso contrário,
passa.

### Catálogo do PostgreSQL
`pg_stats` expõe amostras reais de valores em `most_common_vals` e
`histogram_bounds`.

**Corrigido na Fase 6 (D-039):** o validator recusa `pg_statistic`, `pg_stats`
e as demais relações de estatística. A mitigação por privilégio de role
continua valendo como segunda camada, mas deixou de ser a única.

O resto do catálogo permanece legível, e isso é reconhecimento de schema
aceito — ver F-06 em `docs/SECURITY-REVIEW.md`.

## Resultado esperado

Nenhum cenário da seção "cobertos" deve permitir acesso não mascarado.
Os riscos aceitos devem ter teste que documenta o comportamento atual, para
que uma mudança futura seja percebida.

---

## Resultado medido (Fase 6)

`docs/SECURITY-REVIEW.md` substitui a expectativa deste documento pelo que foi
efetivamente medido. Resumo do que **não** se confirmou como coberto:

| cenário deste documento | resultado real |
|---|---|
| Alias | coberto (Fase 3) |
| SELECT *, JOIN, subquery, CTE, view que preserva nome | cobertos |
| Alias combinado com subquery | **coberto** — a origem sobrevive |
| UNION | coberto por nome; **com alias, vaza** (F-02) |
| Expressões e funções SQL | **vaza** — F-01, mais amplo do que se supunha |
| Erros | coberto |
| Logs, metadata | cobertos |
| Alteração de regras pelo cliente | coberto |
| — | **novo:** `pg_stats` vazava valores reais (F-05, corrigido) |
| — | **novo:** exception alcançável por alias (F-08) |
| — | **novo:** função de usuário devolve coluna sensível (F-04) |
| — | **novo:** perda de catálogo em runtime vazava (F-09, corrigido) |
