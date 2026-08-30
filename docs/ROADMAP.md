# Implementation Roadmap

> **Documento histórico.** As seis fases estão concluídas, mais a Fase 6.1 de
> hardening. Para o estado atual e os próximos passos, leia `docs/HANDOFF.md`.
>
> Cada seção abaixo registra o escopo original **e** o que a medição obrigou a
> corrigir no plano — é aí que está o valor de reler isto.

Seis fases. Cada fase termina com testes verdes, revisão de segurança e busca
ativa de bypass. Não avançar de fase com teste falhando.

---

## FASE 1 — Config Loader + Masking Engine puro

Escopo: núcleo offline, sem banco e sem MCP.

- loader de `masking.yaml` com validação Pydantic
- fail-closed: erro de schema, transformer inexistente, regex inválida ou
  parâmetro ausente impedem a inicialização
- carregamento da chave HMAC via secret/env
- `Matcher`: `contains` e `exact`, case-insensitive por default
- `ExceptionMatcher` com prioridade absoluta
- `TransformerRegistry` extensível
- transformers: md5, sha256, sha512, hmac_sha256, regex, random, fixed,
  truncate
- pipeline EXCEPTION → MASKING → ORIGINAL, default ALLOW
- preservação de NULL

Critérios de aceite: ver seção final deste documento.

---

## FASE 2 — PostgreSQL Adapter + ResultSet Masking

- conexão via psycopg3
- execução de SELECT
- extração de `output_name` de `cursor.description`
- aplicação do Masking Engine sobre o result set
- sanitização de erros do PostgreSQL

Aceite:
- `SELECT cpf FROM cliente` retorna valor mascarado
- `SELECT *` mascara todas as colunas que casam regra
- `SELECT cpf, email` aplica transformers distintos por coluna
- NULL permanece NULL no result set real
- nenhum erro do PostgreSQL chega ao chamador com texto original
- nenhum valor sensível aparece em log

Nesta fase `origin_name` ainda não existe: `SELECT cpf AS documento` **passa
em claro**, e isso deve estar coberto por um teste que documenta a lacuna.

---

## FASE 3 — Column provenance/lineage e proteção contra alias

- resolução de `origin_name` via `table_oid` + `table_column` de
  `cursor.description`, cruzados com `pg_attribute`
- `ColumnDescriptor` completo entregue ao Masking Engine
- matching por `output_name` OR `origin_name`
- exceptions avaliadas contra os dois nomes
  (revisto na Fase 6.1: passaram a ser avaliadas contra o nome **autoritativo**,
  porque casar pelo `output_name` era um bypass — D-042)

Aceite:
- `SELECT cpf AS documento` retorna mascarado
- alias em JOIN, subquery, CTE e view retornam mascarados
- expressão (`ftable = 0`) não quebra o pipeline: `origin_name` é `None` e
  o matching recai sobre `output_name`
- o teste da lacuna da Fase 2 é invertido para o comportamento correto

Primeira tarefa da fase: mapear empiricamente o que o PostgreSQL devolve em
`ftable` para alias, `SELECT *`, JOIN, subquery, CTE, UNION e view. O
design do resolver segue o resultado medido, não a suposição.

**Concluída.** Correções que a medição impôs ao plano original:

- `table_oid`/`table_column` **não** estão em `cursor.description`. Estão em
  `cursor.pgresult.ftable(i)` / `ftablecol(i)`.
- **UNION não preserva proveniência** (`ftable = 0`). O critério "alias em
  UNION → masked" não é alcançável por metadata e foi removido do aceite;
  o comportamento real está fixado em teste e registrado em
  `docs/FUTURE-HARDENING.md`.
- View aponta para a coluna **da view**, não da tabela base. Lineage recursivo
  ficou fora de escopo (D-022).
- `cpf::text` **preserva** a proveniência: cast para o mesmo tipo não cria
  expressão.

---

## FASE 4 — SQL validation + read-only + timeout + row limit

- parsing com pglast, allowlist: somente `SelectStmt` na raiz
- inspeção recursiva de CTEs (bloquear CTE modificadora de dados)
- bloqueio de múltiplos statements
- role PostgreSQL read-only documentada e verificada
- `statement_timeout`
- limite máximo de linhas por resposta

Aceite:
- INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE
  rejeitados
- `WITH x AS (DELETE ... RETURNING *) SELECT * FROM x` rejeitado
- `SELECT 1; DROP TABLE t` rejeitado
- query longa interrompida pelo timeout
- resposta truncada no limite de linhas, com indicação de truncamento
- tentativa de escrita que passe pelo validator ainda falha pelo privilégio

**Concluída.** Acrescentado ao escopo original, a partir de medição:

- **`SELECT 1 INTO nova` parseia como `SelectStmt` e cria uma tabela.** Raiz
  SELECT não basta: `IntoClause` e `LockingClause` são recusadas em qualquer
  ponto da árvore (D-031).
- Contagem de statements pelo que o parser reconhece como executável, não por
  `;`: `SELECT 1;;` é um statement, `;` é nenhum.
- Política de funções `pg_`-deny-by-default (D-027), com o limite de segurança
  declarado.
- Capability check de proveniência, fatal no startup (D-026).

---

## FASE 5 — MCP Server

- servidor MCP expondo a capacidade de consulta
- handlers finos: nenhuma regra de masking neles
- nenhuma superfície que permita ao cliente ler, alterar ou desabilitar regras
- logging estruturado apenas com metadata

Aceite:
- fluxo end-to-end com cliente MCP real
- inspeção do código confirma que nenhum caminho devolve valor original antes
  do Masking Engine
- tentativa do cliente de alterar configuração é rejeitada

**Concluída.** SDK oficial `mcp` 2.1.1, transporte stdio apenas. Ajustes que a
medição impôs ao escopo:

- **Argumentos extras são ignorados pelo SDK, não recusados** (D-037). Nada foi
  remendado; o que se testa é que nenhum extra altera o resultado.
- Auditoria sem digest da SQL: seria um oráculo sobre predicados (D-035).
- Provenance não é exposta ao cliente (D-033).

---

## FASE 6 — Adversarial/security testing

- execução do `PROMPT-03-SECURITY-AUDIT.txt` contra o código pronto
- suíte adversarial completa derivada de `docs/THREAT-MODEL.md`
- varredura automatizada garantindo que nenhum valor original aparece em
  resposta, log ou exceção
- teste de regressão para cada achado
- confirmação de que cada risco aceito está documentado e coberto por teste
  de comportamento

**Concluída.** Relatório em `docs/SECURITY-REVIEW.md`: 11 findings, dois
corrigidos (`pg_stats` expondo valores reais; perda de catálogo em runtime
vazando em claro), nove aceitos com teste que fixa o comportamento.

Suíte `tests/security/`, 209 testes, classificados como BLOCKED, MASKED ou
KNOWN LIMITATION. Bypass conhecido é teste que **afirma** o bypass, nunca
`skip` (D-041).

Ao final da Fase 6, três bypasses de uma linha de SQL permaneciam abertos —
expressão, UNION com alias e alias para o nome de uma exception. As propostas
de correção ficaram no relatório, não implementadas nesta fase por alterarem
semântica documentada do produto.

**Os três foram fechados na Fase 6.1** (D-042 e D-043), na seção seguinte.

---

## Critérios de aceite da FASE 1

Funcionais:

1. `masking.yaml` válido carrega e produz configuração imutável.
2. YAML malformado, transformer desconhecido, regex inválida, `mode`
   inválido ou parâmetro obrigatório ausente **impedem a inicialização**, com
   mensagem que identifica a regra sem expor dados.
3. Regra `cpf` casa `cpf`, `CPF`, `Cpf`, `cPf`, `num_cpf`, `cod_cpf`,
   `cliente_cpf`, `cpf_cliente`, `nr_cpf`.
4. Exception `tipo_cpf` em modo `exact` faz `tipo_cpf` passar original,
   enquanto `cpf` e `num_cpf` continuam mascarados.
5. Exception tem prioridade sobre masking em todos os casos de conflito.
6. Coluna sem correspondência retorna o valor original (default ALLOW).
7. NULL retorna NULL em todos os transformers.
8. Cada transformer é testado com: entrada normal, NULL, string vazia,
   Unicode, valor grande e entrada inválida quando aplicável.
9. md5, sha256, sha512, hmac_sha256, regex, fixed e truncate são
   determinísticos: mesma entrada, mesma saída.
10. `random` produz saídas diferentes para a mesma entrada.
11. `hmac_sha256` com chaves diferentes produz saídas diferentes para a mesma
    entrada.
12. Chave HMAC ausente, com regra que a exige, impede a inicialização.
13. Chave HMAC não pode ser definida em `masking.yaml`: se presente lá, o
    carregamento falha.
14. O matching aceita `origin_name = None` sem erro, usando apenas
    `output_name`.

Não funcionais:

15. `masking/` não importa nada de banco, rede ou MCP.
16. Nenhum teste imprime valor original em log ou saída.
17. Todos os testes passam.

---

## FASE 6.1 — Fechamento dos bypasses críticos

Não estava no roadmap original. Nasceu do resultado da Fase 6: três bypasses
de uma linha de SQL impediam considerar o MVP seguro para uso interno.

- exceptions passam a ser avaliadas pelo nome autoritativo (F-08, D-042)
- análise de sensitividade por AST para expressões e UNION (F-01 e F-02, D-043)
- serialização de linha inteira e ambiguidade entre regras: rejeitar (D-044)
- `mode` default das exceptions passa a `exact`, fechando H-1 (D-045)
- resolução dos nomes exportados por CTE e subquery (D-046)

**Concluída.** Seis dos onze findings do red team ficaram RESOLVED. Nenhum HIGH
ou CRITICAL exigindo mudança de código permanece aberto.

---

## FASE 7 — Admin API

**STATUS: PLANEJADA / NÃO INICIADA.**

A especificação inicial foi revista após inspeção do código real. A
implementação ainda não começou: não há módulo `admin/`, dependência FastAPI
nem teste.

Objetivo: criar uma superfície administrativa separada do MCP para
gerenciamento seguro de configuração, policies, status e auditoria.

Decisões arquiteturais já aprovadas: **D-047 a D-053**. As principais —
Admin API não executa SQL, a fonte administrativa é o arquivo validado e não o
runtime compilado, reload reconstrói o runtime inteiro com troca atômica,
proteções estruturais não são editáveis.

**A especificação final será aprovada antes do início.**

---

## FASE 8 — Front-end

**STATUS: NÃO INICIADA.** Depende da Fase 7 — sem Admin API não há o que
consumir.

---

## FASE 9 — Deployment

**STATUS: NÃO INICIADA.** Streamable HTTP, autenticação, OAuth. A ausência de
porta de rede hoje é uma decisão de segurança (D-036), não uma lacuna.

---

## Estado atual

Fases 1 a 6.1 concluídas. Nenhuma fase nova iniciada. Opções em aberto, com
esforço e impacto, em `docs/HANDOFF.md`, seção 10.
