# Future Hardening

Itens **fora do escopo do MVP**. Registrados aqui como riscos conhecidos e
possíveis evoluções, não como pendências de implementação.

O objetivo do MVP é um Data Masking Gateway simples. Vários dos itens abaixo
transformariam o produto numa plataforma de DLP ou de data access governance,
o que não é a intenção atual.

---

## Bloqueio de WHERE sobre dados sensíveis

```sql
SELECT id FROM clientes WHERE cpf LIKE '123%'
```

A coluna não aparece no result set, então o Masking Engine não é acionado. O
predicado funciona como oráculo: consultas sucessivas reconstroem o valor.

Evolução possível: restringir predicados sobre colunas de origem sensível,
permitindo apenas igualdade contra valor já transformado.

## Bloqueio de ORDER BY / GROUP BY sobre dados sensíveis

`ORDER BY cpf` revela a ordem total dos valores. `GROUP BY` sobre coluna
sensível permite inferência por agrupamento.

## Supressão de agregações

Agregados sobre poucos registros identificam indivíduos. Evolução possível:
suprimir resultado quando a contagem do grupo ficar abaixo de um limiar.

## Controle de cardinalidade

Limitar volume e repetição de consultas por sessão, detectando padrões de
extração incremental.

## RBAC

Perfis de regra por usuário ou aplicação. Hoje as regras são globais.

## Column-level GRANT automático

Gerar e aplicar `REVOKE`/`GRANT` por coluna no PostgreSQL a partir do
`masking.yaml`, como camada de defesa independente do Gateway.

## JSONB deep inspection

Percorrer documentos JSONB e mascarar chaves sensíveis internas. Hoje a
coluna JSONB é tratada como valor único: mascarada por inteiro se o nome
casar, ou passada em claro.

## Transformers Python customizados

Carregar código Python definido pelo usuário como transformer. É execução de
código a partir de configuração e exige um modelo de confiança próprio.

## Multi-tenant

Múltiplos conjuntos de regras e conexões isolados no mesmo processo.

---

## Default deny

Não é um item aprovado, mas é a evolução natural do modelo.

Hoje o default é ALLOW: coluna sem correspondência passa em claro. Uma coluna
sensível com nome fora do padrão — `documento`, `doc`, `ni` — vaza em
silêncio.

Evolução possível: `unmatched_policy: allow | mask | deny`, mantendo `allow`
como default para compatibilidade.

## Expressões e funções SQL

`SELECT substr(cpf,1,3) AS x` não casa nenhuma regra e passa em claro. Para
expressões o PostgreSQL não informa origem (`ftable = 0`), então não há lineage
a resolver.

Evolução possível: analisar a árvore da expressão com pglast e propagar a
sensibilidade das colunas referenciadas para a coluna de saída — ou
simplesmente rejeitar expressões que toquem colunas sensíveis.

Este é o bypass residual mais relevante do MVP.

## UNION apaga a proveniência

Medido na Fase 3 (`tests/test_pgresult_metadata.py`):

```sql
SELECT cpf FROM a UNION ALL SELECT cpf FROM b       -- ftable = 0
```

O PostgreSQL não atribui origem única à coluna de saída de um UNION. Com o
nome preservado o `output_name` ainda casa a regra, mas basta um alias:

```sql
SELECT cpf AS documento FROM a UNION ALL SELECT cpf FROM b   -- passa em claro
```

Nem nome nem origem casam. É o bypass mais barato que sobrou depois da Fase 3.

Evolução possível: resolver a proveniência de cada ramo do UNION por AST
(pglast) e unir a sensibilidade — se qualquer ramo for sensível, a coluna de
saída é sensível. Depende do parser da Fase 4.

## View que renomeia a coluna

A proveniência de uma view aponta para a coluna **da view**, não da tabela
base (D-022). Uma view que renomeia apaga o nome original:

```sql
CREATE VIEW v AS SELECT cpf AS documento FROM cliente;
SELECT documento FROM v;    -- origin_name = "documento"
```

Evolução possível: percorrer `pg_rewrite` para resolver a coluna da view até a
tabela base. Não implementado no MVP: exige interpretar a árvore de reescrita
da view, e uma view pode combinar colunas de várias tabelas.

Mitigação operacional atual: cadastrar também os nomes usados pelas views no
`masking.yaml`, ou evitar views que renomeiem colunas sensíveis.

## Cache de proveniência obsoleto após DDL

O cache `(oid, attnum) -> origem` vive enquanto a conexão existir (D-021). Um
`ALTER TABLE ... RENAME COLUMN` durante esse período deixa a entrada obsoleta,
e o matching passa a usar o nome antigo.

O Gateway é read-only sobre schema estável, então não há invalidação. Evolução
possível: TTL curto, ou invalidação por `pg_notify` em eventos de DDL.

## Provenance por AST: o que a Fase 4 mediu

A Fase 4 investigou, por experimento, se a AST do pglast permite **provar** a
origem nos três bypasses conhecidos. Regra aplicada: provenance provada pode
enriquecer `origin_name`; provenance incerta permanece `DERIVED`/`UNKNOWN`.
Origem não se inventa.

### UNION + alias — provável em parte, não implementado

A AST expõe, por ramo do UNION, a lista de alvos:

```text
SELECT cpf AS documento FROM a UNION ALL SELECT cpf FROM b
  larg = [ColumnRef ('cpf',) AS 'documento']
  rarg = [ColumnRef ('cpf',)]
```

Quando o N-ésimo alvo de **todos** os ramos é um `ColumnRef` simples, o nome de
origem é um fato sintático — e como o matching do Gateway é por nome, propagá-lo
seria sound.

Não implementado nesta fase, por três obstáculos concretos:

- **`SELECT *` em qualquer ramo destrói o mapeamento posicional** entre alvos da
  AST e colunas do result set. Sem expandir `*` contra o catálogo, não há como
  saber qual alvo corresponde a qual coluna.
- Ramos com expressão (`SELECT lower(y)`) ou nomes divergentes entre ramos não
  produzem uma origem única.
- Exigiria acoplar `sql/` a `db/`, hoje independentes, para levar a árvore até a
  montagem dos descritores.

Extensão proposta, pequena e delimitada: quando nenhum ramo usa `*`, e o
N-ésimo alvo de todos os ramos é um `ColumnRef` cujo último identificador é o
mesmo, propagar esse nome como `origin_name` com um `provenance_kind` próprio.
Em qualquer outra forma, manter `DERIVED`.

### VIEW que renomeia — não provável pela AST

A definição da view **não aparece** na árvore da consulta: `SELECT documento
FROM cliente_alias_vw` produz apenas um `ColumnRef` e um `RangeVar`. Resolver
exigiria `pg_rewrite` / `pg_get_viewdef` e reparsing da view — um lineage
engine. Permanece adiado, como em D-022.

### Expressões sobre coluna sensível — provável só com resolução de nomes

A AST mostra o `ColumnRef` dentro da expressão:

```text
SELECT substr(cpf,1,3) AS x FROM cliente        refs = [('cpf',)]
SELECT substr(c.cpf,1,3) AS x FROM cliente c    refs = [('c','cpf')]
SELECT substr(x,1,3) AS y FROM (SELECT cpf AS x FROM cliente) t   refs = [('x',)]
```

O terceiro caso mostra o limite: dentro de uma subquery o nome visível é o
alias, e recuperar `cpf` exige resolver escopos — ou seja, o lineage engine.

**Alternativa mais promissora, e mais barata: rejeitar em vez de enriquecer.**
Recusar a consulta quando qualquer `ColumnRef` dentro de uma expressão nomeia
uma coluna que casa uma regra de masking. Isso não precisa de mapeamento
posicional nem de resolução de escopo — é fail-closed e sound na direção
segura. Custo: acoplar o validator à política de masking, e recusar consultas
legítimas como `SELECT length(cpf)`. Fica como o próximo passo de maior valor.

## Role sem acesso a `pg_catalog` desliga a proteção contra alias

A resolução de proveniência consulta `pg_attribute`, `pg_class` e
`pg_namespace`. Sem esse acesso toda coluna cai em `UNKNOWN`, o matching volta
a depender só do `output_name`, e `SELECT cpf AS documento` passa em claro.

A falha é deliberadamente não fatal (D-025): a alternativa seria derrubar toda
consulta por um problema de catálogo. Mas ela é **silenciosa**, porque não há
logging até a Fase 5.

**Resolvido na Fase 4 (D-026):** `check_provenance_capability` roda no
`connect()` e levanta `CapabilityError` quando a role não consegue resolver uma
coluna. O processo não sobe com a proteção desligada.

Permanece futuro: métrica da proporção de colunas `UNKNOWN` em runtime, quando
o `audit/` existir.

## Validação semântica do masking.yaml no boot

Quatro configurações válidas anulam a proteção sem qualquer aviso (detalhes e
testes em `docs/DECISIONS.md`, D-014):

- exception cujo padrão é substring do padrão de uma regra — desliga a regra
- `regex` com replacement identidade — devolve o valor original
- `truncate` com `length` maior que o valor — devolve o valor original
- `random` com `preserve_length: true` — publica o comprimento do original

Evolução possível: um `--check` de configuração que emita aviso nesses casos, e
um modo estrito que recuse subir. Não foi implementado no MVP porque a detecção
genérica de "transformer inócuo" não é decidível e geraria falso positivo em
configuração legítima.

## Acesso ao catálogo do PostgreSQL

`pg_stats` expõe amostras reais de valores em `most_common_vals` e
`histogram_bounds`. Mitigação atual: privilégios da role read-only.

Evolução possível: denylist explícita de `pg_catalog`, `information_schema` e
`pg_stats` no Query Validator.

## Funções definidas pelo usuário com efeito colateral

A política da Fase 4 (D-027) nega o namespace `pg_` por default e mantém uma
denylist para as famílias perigosas fora dele. Uma função criada pelo usuário,
com nome comum e efeito colateral — `atualiza_saldo()`, `registra_acesso()` —
**passa**.

Fechar isso exigiria resolver cada `FuncCall` contra `pg_proc` e verificar
`provolatile`/`prosecdef`, ou uma allowlist completa por OID. Mitigação atual e
suficiente para o MVP: a role read-only não deve ter `EXECUTE` nessas funções,
e uma função que escreva falha de qualquer forma na transação read-only.

## Inferência por WHERE, ORDER BY e agregação continua aberta

A Fase 4 protege a **execução**, não a inferência. `SELECT id FROM clientes
WHERE cpf LIKE '123%'` continua permitido, e o `statement_timeout` e o
`max_rows` não impedem extração incremental por consultas sucessivas. Ver as
seções acima sobre WHERE/ORDER BY e cardinalidade.
