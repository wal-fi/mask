# Security Review — Fases 6 e 6.1

Red team contra o Gateway completo, com PostgreSQL real e cliente MCP real.
Medido, não suposto: cada finding tem reprodução e teste.

**Atualizado após a Fase 6.1**, que fechou F-01, F-02 e F-08.

Nenhum valor ou credencial real aparece neste documento. O CPF usado nos testes
é fictício.

Suíte: `tests/security/`, 209 testes. Vereditos: **BLOCKED**, **MASKED**,
**KNOWN LIMITATION**. Nenhum bypass conhecido virou `skip` — e quando a Fase
6.1 os fechou, foram exatamente esses testes que quebraram primeiro (D-041).

---

## Sumário

| # | Finding | Severidade | Status |
|---|---|---|---|
| F-01 | Expressão sobre coluna sensível devolve o valor em claro | **HIGH** | **RESOLVED** (6.1, D-043) |
| F-02 | UNION com alias apaga nome e origem | **HIGH** | **RESOLVED** (6.1, D-043) |
| F-08 | Alias para o nome de uma exception desmascara | **HIGH** | **RESOLVED** (6.1, D-042) |
| F-05 | `pg_stats` / `pg_statistic` expõem valores reais | **CRITICAL** | **RESOLVED** (6, D-039) |
| F-09 | Perda de acesso ao catálogo após o startup vazava em claro | **HIGH** | **RESOLVED** (6, D-040) |
| F-11 | Exception com `mode` default desliga a regra (H-1) | **MEDIUM** | **RESOLVED** (6.1, D-045) |
| F-04 | Função de usuário devolve coluna sensível sob nome inócuo | **HIGH** | ACCEPTED RISK — mitigação por privilégio |
| F-07 | Oráculo por predicado reconstrói o valor | **HIGH** | ACCEPTED RISK — fora do escopo do MVP |
| F-03 | View que renomeia coluna apaga o nome original | **MEDIUM** | ACCEPTED RISK — proposta em aberto |
| F-06 | Catálogo permite reconhecimento de schema | **LOW** | ACCEPTED RISK |
| F-10 | Argumentos extras do MCP são ignorados, não recusados | **LOW** | ACCEPTED RISK (D-037) |

**Seis findings corrigidos** (um CRITICAL, quatro HIGH, um MEDIUM); cinco
aceitos, todos com teste que fixa o comportamento.

Nenhum finding HIGH ou CRITICAL exigindo mudança de código permanece aberto.
Os dois HIGH restantes têm mitigação operacional (F-04) ou estão fora do
escopo declarado do MVP (F-07).

---

## F-05 — `pg_stats` expõe valores reais das colunas · CRITICAL · **RESOLVED**

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

## F-09 — Perda de catálogo após o startup · HIGH · **RESOLVED**

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

## F-01 — Expressão sobre coluna sensível · HIGH · **RESOLVED**

**Ataque** Qualquer expressão que faça o PostgreSQL reportar `ftable = 0`:

```sql
SELECT substr(cpf, 1, 11) AS documento FROM cliente;
SELECT cpf || ''          AS documento FROM cliente;
SELECT upper(cpf)         AS documento FROM cliente;
SELECT cpf::varchar       AS documento FROM cliente;
SELECT min(cpf)           AS documento FROM cliente;
SELECT reverse(cpf)       AS documento FROM cliente;   -- reversível
SELECT encode(convert_to(cpf,'UTF8'),'base64') AS d FROM cliente;
```

**Impacto (antes)** O valor original chegava ao cliente, verbatim ou em forma
trivialmente reversível.

**Correção (Fase 6.1, D-043)** `maskgw.sql.sensitivity` analisa a AST da
consulta já validada e determina, por posição do result set, qual regra de
masking cobre as colunas referenciadas. O transformer dessa regra é aplicado ao
**resultado da expressão**.

Funciona porque as regras são globais por nome de coluna: basta o nome, que
está na própria árvore. Não há lineage engine.

**Verificado MASKED:** `substr`, `concat`, `||`, `upper`, `lower`, `lpad`,
`trim`, `coalesce`, `CASE`, `min`, `max`, `ARRAY[]`, `array_agg`, `json_agg`,
`string_agg`, `to_json`, `::varchar`, `::char`, `::jsonb`, `format`, subquery
escalar, referência qualificada (`c.cpf`), expressão aninhada, `reverse`,
base64, hex — mais os nomes escondidos por alias de CTE e de subquery (D-046).

**Verificado REJECTED:** `row_to_json(c)` e `to_json(c)` (linha inteira, D-044);
`concat(cpf, email)` e equivalentes (duas regras diferentes, D-043).

**Verificado sem over-masking:** `substr(tipo_cpf,1,3)` segue original — a
análise respeita a exception sobre o nome referenciado; `upper(nome)` e
`count(*)` seguem originais.

**Reprodução** `tests/security/test_attack_expressions.py`,
`tests/test_sensitivity.py`.

**Limitação residual** A análise casa por nome, sem resolver escopo. Um nome
exportado por uma subquery afeta a consulta inteira — o que mascara demais em
casos raros, nunca de menos. Além de 16 níveis de aninhamento a análise desiste
e a proveniência segue sozinha.

## F-02 — UNION com alias · HIGH · **RESOLVED**

**Ataque**

```sql
SELECT cpf AS documento FROM cliente UNION ALL SELECT 'x';
```

**Impacto (antes)** O PostgreSQL devolve `ftable = 0` para a coluna de saída de
um UNION. Com alias não sobrava nem nome nem origem, e o valor saía em claro.
Era o bypass mais barato que existia.

**Correção (Fase 6.1, D-043)** A análise achata os ramos do set operation —
`UNION`, `UNION ALL`, `INTERSECT`, `EXCEPT`, aninhados — e olha o alvo
correspondente em **todos** eles. Basta um ramo ter dependência sensível
comprovada para a posição inteira ser tratada como sensível: um UNION mistura
as linhas dos ramos numa coluna só.

**Verificado MASKED:** alias no primeiro ramo, alias com ramo inocente, alias
com literal, sensível apenas no segundo ramo, UNION aninhada, UNION dentro de
CTE, UNION dentro de subquery, `UNION` sem `ALL`, `INTERSECT`, `EXCEPT`.
Posições não sensíveis na mesma consulta seguem intactas.

**Verificado REJECTED:** duas classes sensíveis com transformers diferentes na
mesma posição (`SELECT cpf FROM a UNION ALL SELECT email FROM b`).

**Verificado preservado:** `SELECT * FROM a UNION ALL SELECT * FROM b` continua
protegido por nome — as contagens de posição divergem e a proveniência segue
sozinha, sem heurística frágil.

**Reprodução** `tests/security/test_attack_union_views.py::TestUnionIsNowMasked`
e `::TestUnionWithConflictingRules`.

## F-08 — Alias para o nome de uma exception · HIGH · **RESOLVED**

**Ataque**

```sql
SELECT cpf AS tipo_cpf FROM cliente;
```

**Impacto (antes)** Exceptions eram avaliadas contra `output_name` **e**
`origin_name`, com prioridade absoluta. Como o `output_name` é escolhido pelo
atacante, **toda exception configurada era uma primitiva de desmascaramento**
para qualquer coluna sensível.

**Correção (Fase 6.1, D-042)** A exception passou a ser avaliada contra o nome
**autoritativo** da coluna: `origin_name` quando existe, `output_name` só
quando não há origem resolvível. O masking continua avaliando os dois nomes —
a assimetria é o ponto: o alias pode adicionar proteção, nunca removê-la.

| consulta | antes | agora |
|---|---|---|
| `SELECT tipo_cpf FROM cliente` | original | original |
| `SELECT tipo_cpf AS documento` | original | original |
| `SELECT cpf AS tipo_cpf` | **em claro** | mascarado |
| `SELECT cliente_cpf AS tipo_cpf` | **em claro** | mascarado |
| `SELECT substr(cpf,1,11) AS tipo_cpf` | **em claro** | mascarado |

A última linha combina F-01 e F-08: a análise de AST vem antes da exception no
pipeline, justamente para que um alias não libere uma expressão provada
sensível.

Variações de caixa (`TIPO_CPF`, `Tipo_Cpf`) e `mode: exact` continuam se
comportando como documentado.

**Reprodução** `tests/security/test_attack_protocol.py::TestExceptionAbuse`,
`tests/test_engine.py::TestExceptionPriority`.

**Mudança de semântica** A regra `EXCEPTION > MASKING` continua valendo, mas
sobre o nome autoritativo, e não sobre qualquer nome. Documentado em
`docs/MASKING-SPEC.md` e `docs/DECISIONS.md` (D-042).

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

## F-11 — Exception com `mode` default (H-1) · MEDIUM · **RESOLVED**

**Configuração vulnerável**

```yaml
exceptions:
  - match: cpf        # mode default era `contains`
```

**Impacto (antes)** Desligava a regra `cpf` inteira, em silêncio. Aberto desde
a Fase 1 (D-014).

**Correção (Fase 6.1, D-045)** O default de `mode` passou a ser `exact` para
exceptions, mantendo `contains` para regras de masking. A assimetria é
justificada: uma regra larga protege demais, uma exception larga protege de
menos.

Uma exception larga continua possível — mas agora exige `mode: contains`
escrito no arquivo, e a escolha fica visível.

**Compatibilidade** Configuração existente que dependa de exception por
substring muda de comportamento. `config/masking.yaml` do repositório já
declarava `mode: exact` e não mudou.

**Reprodução** `tests/test_config_hazards.py::TestBroadExceptionDisablesRule`.

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
| Protocolo MCP | **BLOCKED, com uma ressalva** — tool desconhecida, `sql` ausente/null/lista/objeto/inteiro/booleano recusados pelo schema; consulta aninhada em 200 níveis não derruba o processo. Payload grande: ver a limitação abaixo |
| Concorrência | **OK** — 30 chamadas paralelas: nenhum erro, mascaramento consistente, nenhuma resposta trocada, 20 `request_id` distintos |
| Row limit | **OK** — valor sensível colocado exclusivamente na linha N+1 não aparece no resultado, no log nem em exceção |
| Escrita | **BLOCKED** — a transação read-only barra INSERT/UPDATE/DELETE/DDL inclusive via função de usuário; tabela verificada intacta por conexão de controle |
| Filesystem administrativo (Etapa 5) | **PREPARADO, NÃO EXPOSTO** — lock entre processos, symlink/tipo/modo inseguros, colisão `O_EXCL`, órfãos, corridas de digest e falhas antes/depois do `replace` têm testes; HTTP/admin ainda não existe |

### Limitação: payload grande depende do tamanho da pilha, e não há proteção

A linha do protocolo MCP **não** afirma que qualquer payload é seguro. Uma
consulta com 100.000 termos somados faz o walk recursivo da AST estourar a
pilha da thread e **derruba o interpretador** com `Windows fatal exception:
stack overflow`, antes de qualquer limite do produto.

O que decide o desfecho é o tamanho de pilha disponível na thread que atende a
chamada, não uma verificação do Gateway. Com a pilha default deste host Windows
o processo cai; com `threading.stack_size(64 MiB)` no processo de teste, o
mesmo teste passa. **Não existe controle no produto que limite o tamanho da
consulta ou a profundidade da expressão**, e esta seção não finge que exista.

Medido no commit `d276c22`, anterior à Fase 7, e reproduzido depois: não é
regressão de nenhuma etapa da Admin API. Uma correção real — limitar o tamanho
da consulta na fronteira, ou tornar o walk iterativo — muda comportamento já
entregue e precisa de aprovação própria. Registrada como risco aberto em
`docs/HANDOFF.md`, seção 11, e **não** como finding corrigido.

A revisão da Etapa 5 também confirmou que erros e `repr` não carregam caminho
sensível, bytes da configuração, DSN, SQL, valor ou traceback. A validação de
ACL do Windows não é prometida, filesystem remoto não é suportado e a janela
entre a segunda conferência de digest e `os.replace` permanece uma limitação
portável declarada, não um controle omitido. A suíte adversarial da superfície
HTTP continua reservada à Etapa 11.

---

## O que falta antes de considerar o MVP seguro para uso interno

Atualizado após a Fase 6.1. Duas condições permanecem, e uma delas é
operacional:

1. **Revogar `EXECUTE` de funções** para a role do Gateway (F-04). É a única
   mitigação disponível e **não é o default do PostgreSQL** — `EXECUTE` é
   concedido a `PUBLIC`. Uma função pré-existente que leia coluna sensível
   devolve o valor sob o nome dela, e uma com SQL dinâmica é bypass de leitura
   completo.

   ```sql
   REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
   ```

2. **Aceitar formalmente o oráculo por predicado** (F-07) ou restringir o uso a
   contextos onde reconstrução por consultas sucessivas seja tolerável. Está
   fora do escopo do MVP desde a Fase 1, e fechá-lo é outro produto.

Duas recomendações que deixaram de ser bloqueantes, mas continuam valendo:

3. **Evitar views que renomeiem colunas sensíveis** (F-03), ou cadastrar
   também os nomes usados pelas views no `masking.yaml`.
4. **Auditar o `masking.yaml`** contra colunas sensíveis com nome fora do
   padrão — consequência direta do default ALLOW, que não mudou.

### Postura resultante

Os três bypasses de uma linha de SQL — expressão, UNION com alias, alias para
exception — estão fechados, junto com o dump de `pg_stats` e a perda silenciosa
de catálogo. Um cliente que conheça os nomes das colunas não consegue mais
extrair valores protegidos por consulta direta.

O que resta exige uma pré-condição fora do controle do cliente (uma função
pré-existente, uma view que renomeia) ou muitas consultas (o oráculo).

Com as duas condições acima atendidas, o Gateway é adequado a **uso interno com
cliente semi-confiável**, e a margem para cliente pouco confiável melhorou
substancialmente. Continua **não** adequado a exposição externa: não há
autenticação, o transporte é stdio, e o oráculo por predicado permanece aberto.
