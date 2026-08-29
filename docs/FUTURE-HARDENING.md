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
expressões o PostgreSQL não informa origem, então não há lineage a resolver.

Evolução possível: analisar a árvore da expressão com pglast e propagar a
sensibilidade das colunas referenciadas para a coluna de saída — ou
simplesmente rejeitar expressões que toquem colunas sensíveis.

Este é o bypass residual mais relevante do MVP.

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
