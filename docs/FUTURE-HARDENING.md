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

> **Histórico (pré-Fase 6.1).**

`SELECT substr(cpf,1,3) AS x` não casava nenhuma regra e passava em claro. Para
expressões o PostgreSQL não informa origem (`ftable = 0`), então não há lineage
a resolver.

Evolução possível: analisar a árvore da expressão com pglast e propagar a
sensibilidade das colunas referenciadas para a coluna de saída — ou
simplesmente rejeitar expressões que toquem colunas sensíveis.

**RESOLVIDO na Fase 6.1 (D-043).** A análise de AST identifica de quais colunas
a expressão depende e aplica a regra delas ao resultado. A opção de *rejeitar*
foi descartada em favor de *mascarar*: recusar `SELECT length(cpf)` seria caro
demais para o uso legítimo.

Permanece aberto o caso em que a expressão referencia um nome que a análise não
consegue associar a regra alguma — ver a limitação de escopo no fim deste
documento.

## UNION apaga a proveniência

> **Histórico (pré-Fase 6.1).** O diagnóstico abaixo continua correto sobre o
> que o PostgreSQL informa; o efeito no Gateway foi corrigido.

Medido na Fase 3 (`tests/test_pgresult_metadata.py`):

```sql
SELECT cpf FROM a UNION ALL SELECT cpf FROM b       -- ftable = 0
```

O PostgreSQL não atribui origem única à coluna de saída de um UNION. Com o
nome preservado o `output_name` ainda casa a regra, mas basta um alias:

```sql
SELECT cpf AS documento FROM a UNION ALL SELECT cpf FROM b   -- passava em claro
```

Era o bypass mais barato que existia depois da Fase 3.

**RESOLVIDO na Fase 6.1 (D-043)**, exatamente pela evolução que esta seção
previa: a análise achata os ramos do set operation e avalia cada posição em
todos eles; um ramo sensível torna a posição sensível. Classes sensíveis
conflitantes na mesma posição são rejeitadas.

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
legítimas como `SELECT length(cpf)`.

**Resolvido na Fase 6.1 (D-043), mas por outro caminho.** A opção de *recusar*
foi trocada por *mascarar*: a regra da coluna referenciada é aplicada ao
resultado da expressão. Recusar `SELECT length(cpf)` seria caro demais para o
uso legítimo, e mascarar fecha o vazamento igualmente. A recusa ficou reservada
aos casos em que não há transformer único comprovável — ambiguidade entre duas
regras e serialização de linha inteira.

## Role sem acesso a `pg_catalog` desliga a proteção contra alias

> **Histórico (pré-Fase 6).** O diagnóstico continua correto; o comportamento
> descrito abaixo mudou duas vezes desde então.

A resolução de proveniência consulta `pg_attribute`, `pg_class` e
`pg_namespace`. Sem esse acesso toda coluna caía em `UNKNOWN`, o matching
voltava a depender só do `output_name`, e `SELECT cpf AS documento` passava em
claro.

A falha era deliberadamente não fatal (D-025): a alternativa seria derrubar
toda consulta por um problema de catálogo. Mas era **silenciosa**, porque não
havia logging até a Fase 5.

**Resolvido em duas etapas.**

1. **Fase 4 (D-026)** — `check_provenance_capability` roda no `connect()` e
   levanta `CapabilityError` quando a role não consegue resolver uma coluna. O
   processo não sobe com a proteção desligada. Isso cobre a *instalação*.
2. **Fase 6 (D-040)** — a falha de catálogo **em runtime** passou a rejeitar a
   consulta, em vez de cair em `UNKNOWN` e default ALLOW. Medido: um Gateway
   que perdia o acesso *depois* do startup voltava a devolver
   `SELECT cpf AS documento` em claro, em silêncio.

`DERIVED` (`ftable = 0`) continua sendo estado legítimo e segue o fluxo normal
— a distinção entre "o PostgreSQL afirma que não há origem" e "não conseguimos
resolver" é o que torna as duas correções compatíveis.

Permanece futuro: métrica da proporção de colunas `UNKNOWN` em runtime, agora
que o `audit/` existe.

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
`histogram_bounds`.

**Resolvido na Fase 6 (D-039):** o validator recusa `pg_statistic`, `pg_stats`
e as demais relações de estatística. O resto do catálogo permanece legível —
bloquear `pg_catalog` inteiro impediria uso legítimo sem fechar os bypasses que
realmente importam. Ver F-05 e F-06 em `docs/SECURITY-REVIEW.md`.

## Endurecer `allowed_pg_functions` no carregamento do arquivo

Levantado ao especificar a Fase 7, e **deliberadamente deixado fora dela**.

`SqlPolicy.allows` avalia, nesta ordem: `denied_functions` →
`denied_prefixes` → allowlist do namespace `pg_`. Como `pg_read_file` **não**
está em `DEFAULT_DENIED_FUNCTIONS` nem casa um prefixo negado, uma
configuração com `sql.allowed_pg_functions: ["pg_read_file"]` **o libera** —
e com ele a leitura de arquivos do servidor pela role do Gateway.

Hoje isso exige acesso de escrita ao `masking.yaml`, ou seja, alguém que já é
dono da máquina. Não é escalação de privilégio; é uma configuração válida que
desliga uma proteção sem qualquer aviso, na mesma família dos quatro hazards
de D-014.

**A Fase 7 fecha o caminho por HTTP** tornando o campo somente leitura na
Admin API (D-050), e **não toca no loader** — endurecê-lo mudaria o
comportamento de um produto já entregue, e isso precisa de decisão própria.

Evolução possível: um conjunto de funções nunca-liberáveis — acesso a arquivo,
execução de programa, controle de backend, replicação, leitura de configuração
— que `allowed_pg_functions` não consiga alcançar, com o carregamento falhando
fechado quando tentar. Custo: pequeno. Impacto: recusa configuração hoje
aceita, então é mudança incompatível.

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

---

## Propostas abertas do red team

Medidas e desenhadas na Fase 6, **não implementadas**, por alterarem a
filosofia do produto ou exigirem lineage. Detalhes, impacto e reprodução em
`docs/SECURITY-REVIEW.md`.

| finding | proposta | status |
|---|---|---|
| F-01 expressão | mascarar o resultado da expressão com a regra da coluna referenciada | **implementado na Fase 6.1** (D-043) — a solução foi mascarar, não rejeitar: recusar `SELECT length(cpf)` seria caro demais |
| F-02 UNION | tratar a posição como sensível quando qualquer ramo tem dependência provada | **implementado na Fase 6.1** (D-043) |
| F-08 exception por alias | avaliar exceptions contra o nome autoritativo | **implementado na Fase 6.1** (D-042) |
| F-11 default de exception | `mode` default `exact` para exceptions | **implementado na Fase 6.1** (D-045) |
| F-03 view | resolver via `pg_get_viewdef` até a tabela base | **em aberto** — exige reparsear a definição e mapear posições: lineage engine |
| F-04 funções | resolver `FuncCall` em `pg_proc` e avaliar `provolatile`/`prosecdef` | **em aberto** — gestão de funções do PostgreSQL inteira; mitigação é operacional |
| F-07 inferência | controle de cardinalidade e supressão de agregados | **em aberto** — outro produto |

O que ficou de fora deliberadamente na Fase 6.1:

- **resolução de escopo.** A análise casa por nome, inclusive no mapa de nomes
  exportados por CTE e subquery. Um nome exportado afeta a consulta inteira —
  mascara demais em casos raros, nunca de menos.
- **profundidade além de 16 níveis.** A análise desiste e a proveniência segue
  sozinha. Desistir é diferente de afirmar que é seguro.
