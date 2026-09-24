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

## Cenários fechados na Fase 6.1

> **Histórico.** As quatro seções abaixo descreviam riscos **aceitos** até a
> Fase 6. Foram fechados na Fase 6.1 e estão preservados aqui com o estado
> atual explícito. Detalhes em `docs/SECURITY-REVIEW.md`.

### Expressões e funções SQL — **COBERTO** (F-01, D-043)
`substr(cpf,1,3)`, `upper(cpf)`, `cpf || ''`, `min(cpf)`, `cpf::varchar`,
`reverse(cpf)`, base64, hex

*Antes:* para expressões o PostgreSQL não informa origem (`ftable = 0`), o
matching dependia do `output_name`, e `SELECT substr(cpf,1,3) AS x` passava em
claro. Era o principal bypass residual do MVP.

*Agora:* a análise de AST (`sql/sensitivity.py`) identifica de quais colunas a
expressão depende e aplica a regra delas ao **resultado**. Funciona sem lineage
porque as regras são globais por nome, e o nome está na própria árvore.

- expressão que depende de **uma** regra sensível → **mascarada**
- expressão com **duas regras diferentes** (`concat(cpf, email)`) → **rejeitada**
- **whole-row serialization** (`row_to_json(c)`, `to_json(c)`) → **rejeitada**
- expressão sobre coluna com exception (`substr(tipo_cpf,1,3)`) → original

### UNION + alias — **COBERTO** (F-02, D-043)

*Antes:* `SELECT cpf AS documento FROM a UNION ALL SELECT 'x'` não tinha nem
nome nem origem, e saía em claro. Era o bypass mais barato que existia.

*Agora:* a análise achata os ramos do set operation — `UNION`, `UNION ALL`,
`INTERSECT`, `EXCEPT`, aninhados, em CTE e em subquery — e avalia cada posição
em **todos** eles. Basta um ramo com dependência comprovada para a posição
inteira ser sensível. Classes sensíveis conflitantes na mesma posição
(`cpf` num ramo, `email` no outro) → **rejeitada**.

`SELECT * FROM a UNION ALL SELECT * FROM b` continua protegido por nome: as
contagens de posição divergem e a proveniência segue sozinha, sem heurística.

### Alias para o nome de uma exception — **COBERTO** (F-08, D-042)

*Antes:* exceptions eram avaliadas contra `output_name` **e** `origin_name`.
Como o `output_name` é escolhido pelo atacante, toda exception configurada era
uma primitiva de desmascaramento: `SELECT cpf AS tipo_cpf` saía em claro.

*Agora:* a exception responde pelo **nome autoritativo** — `origin_name` quando
existe, `output_name` apenas sem origem. **Um alias não pode criar exception.**
O masking segue avaliando os dois nomes: o alias pode adicionar proteção, nunca
removê-la.

### Exception com `mode` default amplo — **COBERTO** (F-11/H-1, D-045)

*Antes:* uma exception escrita sem `mode` herdava `contains` e desligava a
regra inteira em silêncio.

*Agora:* o default de `mode` para exceptions é **`exact`**; `contains` continua
sendo o default das regras de masking. Uma exception larga ainda é possível,
mas exige `mode: contains` escrito no arquivo — a escolha fica visível.

## Riscos conhecidos e aceitos no MVP

Documentados, não corrigidos nesta versão. Ver `docs/FUTURE-HARDENING.md` e
`docs/SECURITY-REVIEW.md`.

### View que renomeia coluna sensível — F-03
`CREATE VIEW v AS SELECT cpf AS documento FROM cliente`

A proveniência aponta para a coluna **da view**, não da tabela base, e a
definição da view não está na árvore da consulta. Nem a AST nem a proveniência
enxergam `cpf`. Resolver exigiria reparsear `pg_get_viewdef` e mapear posições.

### Função de usuário e SECURITY DEFINER — F-04

Uma função **pré-existente** que leia coluna sensível devolve o valor sob o
nome dela, que não casa regra. `SECURITY DEFINER` executa com o privilégio do
dono. Uma função com SQL dinâmica é bypass de leitura completo.

O atacante não consegue criá-la — `CREATE` é recusado e a transação é
read-only. Mitigação é **privilégio, não código**: revogar `EXECUTE`, que é
concedido a `PUBLIC` por padrão.

### WHERE / ORDER BY como oráculo — F-07
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
passa em claro — consequência direta do default ALLOW, que **não** mudou.

A proteção depende da qualidade do `masking.yaml`. A análise de AST da Fase 6.1
não ajuda aqui: ela propaga a sensibilidade de um nome que casa regra, e aqui
nenhum nome casa.

### Reconhecimento de schema pelo catálogo — F-06
`pg_class`, `pg_attribute`, `pg_proc`, `pg_views`, `pg_roles`, `pg_settings` e
`information_schema` seguem legíveis. Uma IA enumera tabelas, colunas, funções
e a definição das views.

Aceito deliberadamente: é metadata, não dado. A distinção que importa — metadata
sim, amostras de valores não — já está aplicada com o bloqueio das relações de
estatística.

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

## Fase 9 — ameaças aprovadas do plano PGWire e multi-datasource

**Estado:** threat model aprovado em 2026-09-22; a superfície de listener e
Admin UX ainda não foi implementada. A Etapa 2 implementa o
store/modelo/destino/migração e a Etapa 3 o registry e o lifecycle (itens 10–12
abaixo, no nível do registry), cada uma coberta em sua validação própria. A
Etapa 4 expõe o catálogo pela Admin API local (`/admin/v2`): o administrador
autenticado fornece destino e segredo; SSRF/rebinding, destino lento ou hostil,
corrida administrativa, falha de persistência e vazamento em erro/auditoria
foram exercitados em `docs/PHASE-9-STAGE-4-VALIDATION.md`. Um administrador
com o token pode sondar a rede privada pelos testes de candidato (destino
recusado × conexão falha × capability ausente); é o mesmo principal que já
configura destinos, e o plano administrativo continua somente em loopback.

A Fase 9 transforma o Gateway em servidor PostgreSQL perante clientes de IDE e
adiciona destinos administráveis. Isso cria atacantes e ativos novos:

- cliente TCP não autenticado controla framing, timing e mensagens de startup;
- cliente autenticado controla SQL, prepared statements, parâmetros, formatos
  e cancelamentos;
- administrador controla host/porta/database/usuário e fornece segredo upstream;
- destino cadastrado pode ser hostil, lento, mudar DNS ou produzir metadata e
  erros malformados;
- atacante local pode copiar ou alterar o store cifrado;
- IDE executa consultas automáticas que não foram escritas conscientemente pelo
  usuário.

### Premissas de confiança e limites

- O cliente TCP, a IDE e o usuário SQL são não confiáveis; autenticação não
  transforma o principal único do MVP em autorização por datasource.
- O processo do Gateway e o secret provider que entrega a chave-mestra são
  confiáveis. Um atacante que controla o processo, o ambiente ou a chave pode
  ler segredos em memória e está fora desta fronteira.
- O atacante local considerado pode copiar ou alterar o arquivo do catálogo,
  mas não pode alterar a âncora monotônica confiável implementada pela Etapa 2
  fora do arquivo substituível. O diretório da âncora é um trust boundary
  operador-gerenciado; se ele também for substituído, replay integral continua
  fora da garantia local e não é alegado como coberto.
- O destino upstream pode ser lento ou hostil, mas a política de rede e a
  validação de resolução precisam impedir SSRF, rebinding e destinos proibidos.

### Ativos adicionais

- senha/verifier do principal do Gateway;
- credenciais upstream de todos os datasources;
- chave-mestra e nonces;
- associação alias → destino real;
- certificados e chave privada TLS;
- mapa de sessões, cancel keys, prepared statements e parâmetros;
- disponibilidade de sockets e conexões upstream.

### Fronteiras adicionais

```text
rede não confiável → TLS/PGWire → sessão autenticada → alias/runtime
Admin UI → Admin API v2 → validação de destino → store cifrado
store cifrado + master key → segredo em memória → PostgreSQL upstream
```

### Cenários obrigatórios

1. **Parser de protocolo:** comprimentos negativos/excessivos, frames truncados,
   UTF-8 inválido, mensagem fora de ordem e desync não causam alocação sem teto,
   traceback, hang ou execução parcial.
2. **Autenticação:** usuário, alias e senha inválidos são indistinguíveis onde
   necessário; comparação não cria oráculo e brute force recebe limite.
3. **TLS:** bind externo não inicia sem TLS; SSLRequest não permite downgrade;
   certificado/chave inválidos falham antes de qualquer plano de dados.
4. **Máquina extended query:** SQL é validado no `Parse`, identidade é congelada
   até `Bind/Execute`, parâmetros nunca viram texto SQL e erro exige `Sync`.
5. **Cancelamento:** chave de uma sessão não cancela outra e valores inválidos
   não confirmam existência.
6. **Tipos/formato:** binário, OID, typmod e valores malformados não pulam
   masking; coluna transformada não conserva tipo enganoso.
7. **Catálogo de IDE:** nenhuma allowlist ampla de `pg_`; introspecção não lê
   arquivo, função de usuário, estatística com amostras, configuração ou segredo.
8. **SSRF:** cadastro não alcança loopback, link-local, multicast, metadata
   cloud ou destino diferente após resolução, salvo exceção local aprovada.
9. **Store:** tamper, truncamento e transplant de ciphertext falham fechado;
   replay de arquivo inteiro só é aceito como coberto com âncora monotônica
   confiável, e sem ela o startup falha fechado. Backup, temporário, erro e
   auditoria não contêm plaintext. Rotação confirmada da chave-mestra não deixa
   backup gerenciado legível pela chave anterior; cópias já obtidas por terceiros
   só perdem valor com a troca das credenciais upstream.
10. **Concorrência:** rename/disable/remove/rotate não troca o destino de uma
    sessão admitida e não fecha recurso ainda referenciado.
11. **Exaustão:** conexões lentas, startup incompleto, idle, prepared statements
    e sessões simultâneas têm limites e cleanup determinístico.
12. **Isolamento:** falha ou reload de um datasource não mistura policies,
    credenciais, conexões ou resultados com outro.

Os requisitos normativos e as etapas estão em `docs/PHASE-9-SPEC.md`; o índice
de cobertura aprovado está em `docs/PHASE-9-TRACEABILITY.md`. Os cenários de
store, cifra, replay, recuperação e SSRF da Etapa 2 foram executados na suíte
local e estão em `docs/PHASE-9-STAGE-2-VALIDATION.md`. Concorrência, exaustão
e isolamento no registry (itens 10–12) estão em
`docs/PHASE-9-STAGE-3-VALIDATION.md`; PGWire e os demais cenários continuam
exigindo a evidência indicada na matriz.

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
