# Security Review — Fase 6

Red team contra o Gateway completo (Fases 1–5), com PostgreSQL real e cliente
MCP real. Medido, não suposto: cada finding tem reprodução e teste.

Nenhum valor ou credencial real aparece neste documento. O CPF usado nos testes
é fictício.

Suíte: `tests/security/`, 170 testes. Vereditos: **BLOCKED**, **MASKED**,
**KNOWN LIMITATION**. Nenhum bypass conhecido virou `skip`.

---

## Sumário

| # | Finding | Severidade | Status |
|---|---|---|---|
| F-01 | Expressão sobre coluna sensível devolve o valor em claro | **HIGH** | ACCEPTED RISK — proposta em aberto |
| F-02 | UNION com alias apaga nome e origem | **HIGH** | ACCEPTED RISK — proposta em aberto |
| F-03 | View que renomeia coluna apaga o nome original | **MEDIUM** | ACCEPTED RISK — proposta em aberto |
| F-04 | Função de usuário devolve coluna sensível sob nome inócuo | **HIGH** | ACCEPTED RISK — mitigação por privilégio |
| F-05 | `pg_stats` / `pg_statistic` expõem valores reais | **CRITICAL** | **CORRIGIDO** (D-039) |
| F-06 | Catálogo permite reconhecimento de schema | **LOW** | ACCEPTED RISK |
| F-07 | Oráculo por predicado reconstrói o valor | **HIGH** | ACCEPTED RISK — fora do escopo do MVP |
| F-08 | Alias para o nome de uma exception desmascara | **HIGH** | ACCEPTED RISK — proposta em aberto |
| F-09 | Perda de acesso ao catálogo após o startup vazava em claro | **HIGH** | **CORRIGIDO** (D-040) |
| F-10 | Argumentos extras do MCP são ignorados, não recusados | **LOW** | ACCEPTED RISK (D-037) |
| F-11 | Exception com `mode` default desliga a regra (H-1) | **MEDIUM** | ACCEPTED RISK — proposta em aberto |

Dois findings corrigidos nesta fase; nove aceitos, todos com teste que fixa o
comportamento.

---

## F-05 — `pg_stats` expõe valores reais das colunas · CRITICAL · CORRIGIDO

**Ataque**

```sql
SELECT attname, most_common_vals FROM pg_stats WHERE tablename = 'cliente';
SELECT stavalues1::text FROM pg_statistic WHERE starelid = 'cliente'::regclass;
```

**Pré-condição** Nenhuma além de acesso à tool e de a tabela ter sido
analisada. `ANALYZE` roda por autovacuum, sem intervenção.

**Impacto** O PostgreSQL guarda **amostras dos valores reais** em
`pg_statistic.stavaluesN`, e `pg_stats` as expõe em `most_common_vals` e
`histogram_bounds`. Uma consulta devolvia CPFs verdadeiros em claro. Não há
reconstrução: é um dump. Os nomes das colunas de saída (`most_common_vals`,
`histogram_bounds`) não casam regra nenhuma, e não há coluna de origem a
resolver — todas as camadas do Gateway passavam batido.

**Proteção existente antes** Nenhuma. Já estava registrado em
`docs/THREAT-MODEL.md` como risco de catálogo, com mitigação delegada a
privilégios de role — que na prática ninguém aplica.

**Status CORRIGIDO.** O validator recusa `pg_statistic`, `pg_stats`,
`pg_stats_ext`, `pg_stats_ext_exprs`, `pg_statistic_ext` e
`pg_statistic_ext_data` por nó `RangeVar`, em qualquer ponto da árvore —
inclusive em CTE, subquery e ramo de UNION. Decide pelo nome da relação, então
`pg_catalog.pg_stats`, `PG_STATS` e `"pg_stats"` caem juntos. Ver D-039.

Isto **não** é um bloqueio de `pg_catalog`: o resto do catálogo continua
legível, e a resolução de proveniência usa a conexão do Gateway, não a SQL do
cliente, então nada nela foi afetado.

**Reprodução** `tests/security/test_attack_functions_catalog.py::TestStatisticsRelationsAreBlocked`
— inclui um teste que prova, por conexão de controle, que o CPF está de fato
nas estatísticas.

---

## F-09 — Perda de catálogo após o startup · HIGH · CORRIGIDO

**Ataque** Não é um ataque via SQL: é uma falha operacional explorável.

**Pré-condição** O Gateway sobe saudável; depois disso a role perde `SELECT`
em `pg_attribute` — por hardening mal calibrado, `ALTER DEFAULT PRIVILEGES`,
troca de role ou migração.

**Impacto** Medido: `SELECT cpf AS documento FROM cliente` passava a devolver
o CPF **em claro, em silêncio**. A resolução falhava, a coluna virava
`UNKNOWN`, e `UNKNOWN` caía no default ALLOW. O capability check da Fase 5 só
roda no `connect()` e não cobria a perda em runtime.

**Proteção existente antes** Apenas o check de startup (D-026).

**Status CORRIGIDO.** Passou a distinguir duas situações que antes eram uma:

| situação | quem afirma | comportamento |
|---|---|---|
| `ftable = 0` (DERIVED) | o PostgreSQL: não há coluna de origem | normal, default ALLOW |
| falha ao consultar o catálogo | erro operacional nosso | **consulta rejeitada** |

O resolver levanta `CapabilityError`, que a fronteira MCP traduz em
`CONFIGURATION_ERROR`. Nada da mensagem do PostgreSQL sai, e nem `__cause__`
nem `__context__` apontam para ela. A falha **não** entra no cache, então um
erro transitório não desliga a proveniência pelo resto da conexão. Ver D-040.

**Impacto da mudança** Uma instalação com catálogo inacessível deixa de
responder consultas em vez de responder errado. Colunas `DERIVED` não são
afetadas. Linha de reversão, se o operador preferir disponibilidade a
correção: voltar `_load` a absorver o erro.

**Reprodução** `tests/security/test_attack_protocol.py::TestCapabilityLossAfterStartup`
— cria uma role real, revoga `pg_attribute`, verifica a rejeição e restaura.

---

## F-01 — Expressão sobre coluna sensível · HIGH · ACCEPTED RISK

**Ataque** Qualquer expressão que faça o PostgreSQL reportar `ftable = 0`:

```sql
SELECT substr(cpf, 1, 11) AS documento FROM cliente;
SELECT cpf || ''          AS documento FROM cliente;
SELECT upper(cpf)         AS documento FROM cliente;
SELECT coalesce(cpf, '')  AS documento FROM cliente;
SELECT cpf::varchar       AS documento FROM cliente;
SELECT row_to_json(t)     AS d         FROM cliente t;   -- a linha inteira
```

**Pré-condição** Conhecer o nome da coluna. `SELECT *` ou o catálogo entregam.

**Impacto** O valor original chega ao cliente, verbatim. `row_to_json` é o
pior caso: devolve a linha inteira, com todas as colunas sensíveis.

Variantes que devolvem forma **reversível**, não o literal —
igualmente exposição: `reverse(cpf)`, `encode(convert_to(cpf,'UTF8'),'base64')`,
`encode(...,'hex')`. Transformado por SQL não é sinônimo de seguro.

**Assimetria medida** `cpf::text` **preserva** a origem e sai mascarado;
`cpf::varchar` não. Um cast para o mesmo tipo é no-op e o PostgreSQL mantém a
proveniência; qualquer outro vira expressão.

**Proteção existente** Nenhuma para este caso. A proveniência da Fase 3 cobre
alias, subquery, CTE, JOIN, cast-no-op e view — não expressões.

**Recomendação (proposta, não implementada)** Rejeitar a consulta quando
qualquer `ColumnRef` dentro de uma expressão nomeie uma coluna que case uma
regra de masking. Não precisa de mapeamento posicional nem de resolução de
escopo, e é fail-closed.

Custo: acopla o validator à política de masking, e recusa consultas legítimas
como `SELECT length(cpf)` ou `SELECT count(cpf)`. Falso-negativo conhecido:
dentro de subquery o nome visível é o alias
(`SELECT substr(x,1,3) FROM (SELECT cpf AS x FROM cliente) t` referencia `x`).
Fechar isso de verdade exige lineage completo.

**Reprodução** `tests/security/test_attack_expressions.py`.

---

## F-02 — UNION com alias · HIGH · ACCEPTED RISK

**Ataque**

```sql
SELECT cpf AS documento FROM cliente UNION ALL SELECT 'x';
```

**Pré-condição** Nenhuma. Uma cláusula a mais em qualquer consulta.

**Impacto** O PostgreSQL devolve `ftable = 0` para a coluna de saída de um
UNION. Com o nome preservado o `output_name` ainda salva; com alias não sobra
nada, e o valor sai em claro. É o bypass mais barato que resta: transforma uma
coluna protegida em coluna aberta com uma linha de SQL.

**Proteção existente** Só o `output_name`, quando o alias não é usado.

**Recomendação (proposta, não implementada)** Quando **nenhum** ramo usa `*`,
e o N-ésimo alvo de **todos** os ramos é um `ColumnRef` simples cujo último
identificador é o mesmo, propagar esse nome como `origin_name`. Em qualquer
outra forma, manter `DERIVED`.

Obstáculo principal: `SELECT *` em qualquer ramo destrói o mapeamento
posicional entre alvos da AST e colunas do result set.

**Reprodução** `tests/security/test_attack_union_views.py::TestUnionBypass`.

---

## F-08 — Alias para o nome de uma exception · HIGH · ACCEPTED RISK

**Ataque**

```sql
SELECT cpf AS tipo_cpf FROM cliente;
```

**Pré-condição** Existir qualquer exception no `masking.yaml`, e o atacante
descobrir o nome — o que o catálogo entrega, já que exceptions costumam
nomear colunas reais.

**Impacto** Exceptions são avaliadas contra `output_name` **e** `origin_name`,
e têm prioridade absoluta. Como o `output_name` é escolhido pelo atacante,
**toda exception configurada vira uma primitiva de desmascaramento** para
qualquer coluna sensível. Variações de caixa funcionam igualmente
(`TIPO_CPF`, `Tipo_Cpf`).

O `mode: exact` continua fazendo o seu trabalho: `meu_tipo_cpf`,
`tipo_cpf_extra` e `" tipo_cpf "` seguem mascarados. O problema não é a
largura da exception — é ela ser alcançável pelo nome de saída.

**Proteção existente** Nenhuma. Este comportamento está documentado como
"prioridade absoluta" desde a Fase 1, e foi fixado em teste na Fase 3.

**Recomendação (proposta, não implementada)** Avaliar exceptions contra
`origin_name` quando ele existir, caindo para `output_name` só quando não há
origem resolvível. Mudança de uma linha no matcher.

| consulta | hoje | com a proposta |
|---|---|---|
| `SELECT tipo_cpf FROM cliente` | original | original (inalterado) |
| `SELECT tipo_cpf AS x FROM cliente` | original | original (inalterado) |
| `SELECT cpf AS tipo_cpf FROM cliente` | **em claro** | mascarado |

Altera uma regra documentada do produto (`EXCEPTION > MASKING`), por isso é
proposta e não correção direta.

**Reprodução** `tests/security/test_attack_protocol.py::TestExceptionAbuse`.

---

## F-04 — Função de usuário com nome inócuo · HIGH · ACCEPTED RISK

**Ataque**

```sql
SELECT safe_lookup();                       -- devolve cpf
SELECT definer_lookup();                    -- SECURITY DEFINER
SELECT dyn('SELECT cpf FROM cliente');      -- SQL dinâmica
```

**Pré-condição** A função **já existir** no banco. O atacante não consegue
criá-la: `CREATE FUNCTION` é recusado pelo validator e a transação é read-only.

**Impacto** A coluna de saída recebe o nome da função (`safe_lookup`), que não
casa regra alguma, e não há origem a resolver. O valor sai em claro.

Três agravantes medidos:

- **SECURITY DEFINER** executa com o privilégio do dono da função. A postura
  read-only do Gateway não a limita, e ela pode ler o que a role do Gateway
  não poderia.
- Uma função com **SQL dinâmica** é um bypass de leitura completo: executa
  SQL arbitrária fora do validator.
- A política de funções (D-027) nega o namespace `pg_`, mas uma função de
  usuário com nome comum passa — como está declarado em `docs/SECURITY.md`.

**Proteção existente** A transação read-only barra o efeito colateral de
**escrita**: `writer()` e `dyn('INSERT ...')` são recusados, e a tabela
permanece intacta (verificado por conexão de controle). A leitura não é barrada.

**Recomendação** Operacional, não de código: a role do Gateway não deve ter
`EXECUTE` em funções de usuário, e `EXECUTE` é concedido a `PUBLIC` por
padrão — é preciso revogar explicitamente:

```sql
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

Resolver no código exigiria consultar `pg_proc` por `FuncCall` e avaliar
`provolatile`/`prosecdef`, ou uma allowlist por OID — fora do escopo.

**Reprodução** `tests/security/test_attack_functions_catalog.py`.

---

## F-07 — Oráculo por predicado · HIGH · ACCEPTED RISK

**Ataque**

```sql
SELECT count(*) FROM cliente WHERE cpf = '<hipótese>';
SELECT count(*) FROM cliente WHERE substr(cpf, 1, 1) = '1';
```

**Pré-condição** Nenhuma.

**Impacto** A coluna sensível não aparece no result set, então o Masking
Engine nunca é acionado — o que vaza é a **resposta do predicado**. A suíte
reconstrói o CPF de 11 dígitos com 11 consultas, um dígito por vez, e a
asserção do teste é a igualdade com o valor original.

`ORDER BY`, `GROUP BY`, `HAVING`, `LIKE` e `LIMIT/OFFSET` sobre a coluna
sensível funcionam igualmente. O `max_rows` limita a saída, não o número de
consultas.

**Proteção existente** Nenhuma, por decisão de escopo. Controle de inferência
está listado como fora do MVP em `docs/FUTURE-HARDENING.md` desde a Fase 1.

**Recomendação** Fora do escopo: exigiria controle de cardinalidade, supressão
de agregados e restrição de predicados sobre colunas sensíveis — um produto
diferente. Mitigação operacional: limitar o volume de consultas por sessão e
auditar padrão de extração incremental. O `audit/` já registra contagem e
duração por consulta, o que é a matéria-prima dessa detecção.

**Reprodução** `tests/security/test_attack_oracle_errors.py::TestInferenceOracle`.

---

## F-03 — View que renomeia coluna · MEDIUM · ACCEPTED RISK

**Ataque**

```sql
CREATE VIEW v2 AS SELECT cpf AS documento FROM cliente;   -- pré-existente
SELECT documento FROM v2;
```

**Pré-condição** A view existir. O atacante não pode criá-la.

**Impacto** A proveniência aponta para a coluna **da view**
(`origin_name = "documento"`, `provenance_kind = VIEW`), não da tabela base. O
nome original desaparece e o valor sai em claro. Vale também para view sobre
view e para view com expressão.

**Proteção existente** Views que **preservam** o nome ficam mascaradas, e alias
sobre elas também.

**Recomendação (proposta, não implementada)** `pg_get_viewdef` está disponível
para a conexão do Gateway — a suíte prova. Resolver exigiria reparsear a
definição e mapear posicionalmente, com o mesmo problema de `SELECT *`: um
lineage engine. Mitigação operacional: cadastrar no `masking.yaml` também os
nomes usados pelas views, ou evitar views que renomeiem colunas sensíveis.

**Reprodução** `tests/security/test_attack_union_views.py::TestViewBypass`.

---

## F-11 — Exception com `mode` default (H-1) · MEDIUM · ACCEPTED RISK

**Ataque** Não é ataque via SQL: é uma configuração que desliga a proteção.

```yaml
exceptions:
  - match: cpf        # mode default é `contains`
```

**Impacto** Desliga a regra `cpf` inteira, em silêncio. Registrado desde a
Fase 1 (D-014, H-1) e fixado em `tests/test_config_hazards.py`.

**Recomendação (proposta, não implementada)** Trocar o default de `mode` para
exceptions de `contains` para `exact`, mantendo `contains` como default das
regras de masking. A assimetria é justificada: regra larga protege demais,
exception larga protege de menos.

Compatibilidade: quebra silenciosamente configurações existentes que dependem
de exception por substring — uma exception `tipo_cpf` continuaria funcionando,
mas uma exception `tipo` que hoje cobre `tipo_cpf` deixaria de cobrir. Migração
sugerida: exigir `mode` explícito nas exceptions por uma versão, recusando o
carregamento quando ausente, e só então mudar o default.

Combina com F-08: a proposta daquele finding reduz o alcance desta, mas não a
elimina.

---

## F-06 — Reconhecimento de schema pelo catálogo · LOW · ACCEPTED RISK

**Ataque** `pg_class`, `pg_attribute`, `pg_proc`, `pg_views`, `pg_roles`,
`pg_settings`, `information_schema`.

**Impacto** Uma IA enumera tabelas, colunas, funções, roles e a definição das
views — o que inclui descobrir quais views renomeiam colunas (F-03) e quais
funções existem (F-04). `pg_settings` revela `data_directory` e outras
configurações operacionais.

**Proteção existente** As relações de estatística estão bloqueadas (F-05). O
restante é metadata, não dado.

**Recomendação** Manter legível. A distinção que importa — metadata sim,
amostras de valores não — já está aplicada. Bloquear `pg_catalog` inteiro
impediria uso legítimo e não fecha F-03 nem F-04, cujas mitigações são outras.

---

## F-10 — Argumentos extras do MCP · LOW · ACCEPTED RISK

Medido no SDK `mcp` 2.1.1: o `input_schema` não declara
`additionalProperties: false`, e o modelo de argumentos usa `extra="ignore"`.
`{"sql": "...", "disable_masking": true}` executa normalmente, com o extra
descartado antes do handler.

**Impacto** Nulo na prática: o extra não altera nada. O que falha é a
expectativa de recusa explícita.

**Status** Sem remendo, conforme D-037. A suíte fixa a garantia que vale: para
cada nome perigoso, o resultado é idêntico ao da chamada limpa e a coluna
continua mascarada.

---

## Superfícies verificadas sem finding

| classe | veredito |
|---|---|
| Erro do PostgreSQL como oráculo | **BLOCKED** — cast inválido, divisão por zero, regex inválida, função que levanta com o valor: nada do servidor chega ao cliente, e `__cause__`/`__context__` ficam nulos |
| Nomes de coluna hostis | **MASKED** — caixa, espaços, `\n`, zero-width, sinal de Kelvin, İ turco, fullwidth e homoglifo cirílico: todos protegidos, os últimos pela origem |
| Serialização | **OK** — bytea não-UTF8 vira base64; JSONB profundo, arrays aninhados, numeric extremo, NaN e Infinity atravessam o MCP; tipos sem forma canônica falham fechado, nunca em `repr()` |
| Segredos | **OK** — a chave HMAC não aparece em `repr` de aplicação, config, política ou gateway, nem em erro, nem na resposta MCP; o DSN não aparece no `repr` do adapter |
| Protocolo MCP | **BLOCKED** — tool desconhecida, `sql` ausente/null/lista/objeto/inteiro/booleano recusados pelo schema; payload grande e consulta aninhada em 200 níveis não derrubam o processo |
| Concorrência | **OK** — 30 chamadas paralelas: nenhum erro, mascaramento consistente, nenhuma resposta trocada, 20 `request_id` distintos |
| Row limit | **OK** — valor sensível colocado exclusivamente na linha N+1 não aparece no resultado, no log nem em exceção |
| Escrita | **BLOCKED** — a transação read-only barra INSERT/UPDATE/DELETE/DDL inclusive via função de usuário; tabela verificada intacta por conexão de controle |

---

## O que falta antes de considerar o MVP seguro para uso interno

Quatro condições, em ordem de importância:

1. **Assumir que o cliente MCP pode ler qualquer valor sensível** cujas colunas
   ele conheça, via F-01, F-02 ou F-08 — três bypasses reproduzíveis com uma
   linha de SQL cada. O Gateway hoje eleva o custo do vazamento acidental; não
   resiste a um cliente adversarial.
2. **Revogar `EXECUTE` de funções** da role do Gateway (F-04). É a única
   mitigação disponível e não é default do PostgreSQL.
3. **Aceitar formalmente o oráculo por predicado** (F-07) ou restringir o uso a
   contextos onde reconstrução por consultas sucessivas seja tolerável.
4. **Auditar o `masking.yaml`** contra H-1 (F-11) e contra colunas sensíveis
   com nome fora do padrão — consequência direta do default ALLOW.

Com isso entendido e aceito, o Gateway é adequado a **uso interno com cliente
semi-confiável**. Não é adequado a cliente hostil nem a exposição externa.
