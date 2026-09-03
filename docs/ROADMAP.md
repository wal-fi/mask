# Implementation Roadmap

> **Documento histórico e registro de andamento.** As seis fases estão
> concluídas, mais a Fase 6.1 de hardening. A Fase 7 está em andamento, com as
> Etapas 1–8 concluídas. Para o estado atual, leia `docs/HANDOFF.md`.
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

**STATUS: EM ANDAMENTO — ETAPAS 1–6 CONCLUÍDAS.**

A implementação segue `docs/PHASE-7-SPEC.md` de forma incremental:

| etapa | estado | commit |
|---|---|---|
| 1 — IDs e revision no modelo do arquivo | concluída | `053cf66` |
| 2 — `RuntimeRegistry` | concluída | `3114c14` |
| 3 — aquisição/liberação de runtime por query | concluída | `3c8de4c` |
| 4 — composition root e lifecycle | concluída | `7c06132` |
| 5 — filesystem seguro: verificações, lock exclusivo, escrita atômica, digest e limpeza de temporários | concluída | `d651fe0` |
| 6 — seção crítica administrativa e fluxo completo de escrita/reload | concluída | `git log -- src/maskgw/admin` |
| 7 — aplicação HTTP/FastAPI e sua segurança e rotas de leitura | concluída | `git log -- src/maskgw/admin/http` |
| 8 — `POST /admin/v1/config:validate` | próxima; não iniciada | — |

A sincronização com `origin/master` deve ser conferida pelo Git, não inferida
deste documento. A Etapa 4 criou `bootstrap/` como composition root, removeu
`gateway/factory.py` e fez os entrypoints `python -m maskgw` e
`python -m maskgw.mcp` delegarem ao bootstrap, preservando MCP stdio.

A Etapa 5 adicionou `config/filesystem.py`: verificações fail-closed, sidecar
lock mantido aberto, digest dos bytes exatos, escrita atômica e limpeza
seletiva de temporários.

A Etapa 6 adicionou `maskgw/admin/` — `errors.py`, `document.py` e
`service.py` — com a seção crítica administrativa e o fluxo de onze passos da
§7.4 fim a fim: adoção, `expected_revision`, digest, limite de aposentados,
validação, compilação, conexão com os capability checks, persistência atômica,
swap, atualização do digest e fechamento do aposentado. O composition root passa
a adquirir o `ConfigFileStore` quando o admin está habilitado por
`build_application(admin_enabled=True)`, e a liberá-lo por último no shutdown.

A Etapa 7 adicionou `maskgw/admin/http/` — a primeira porta de rede do projeto,
opcional e desligada por default. Oito rotas `GET`/`HEAD` sob `/admin/v1`,
autenticação por bearer token só em header, bind exclusivamente em loopback,
as quatro camadas anti-CSRF da §3.3, limite de corpo de 1 MiB que corta
streaming sem bufferizar, `Cache-Control: no-store` em toda resposta, nenhum
header CORS, e os três handlers de erro da §10.3. FastAPI e uvicorn entraram na
stack e são usados só ali — importar `maskgw.admin` continua não os carregando.

O admin passa a ser habilitado por `MASKGW_ADMIN_ENABLED=1`; `build_application`
ganha `admin_http` ao lado de `admin_enabled`, e o segundo implica o primeiro.
O startup confirma o bind antes de liberar o MCP, e o shutdown faz `join` da
thread HTTP antes de fechar os runtimes.

Continua **não havendo** rota de escrita, `config:validate`, adoção com backup
ou `AdminAudit`: são as Etapas 8, 9 e 10, e não foram antecipadas.

Objetivo: criar uma superfície administrativa separada do MCP para
gerenciamento seguro de configuração, policies, status e auditoria.

Decisões arquiteturais já aprovadas: **D-047 a D-054**. As principais —
Admin API não executa SQL, a fonte administrativa é o arquivo validado e não o
runtime compilado, reload reconstrói o runtime inteiro, proteções estruturais
não são editáveis, operações administrativas de escrita são serializadas com
`expected_revision` verificado dentro da seção crítica (D-052), e o ciclo de
vida do runtime é coordenado por refcount + `retired` (D-054).

Uma precisão registrada em D-048: **não há atomicidade conjunta entre
filesystem e memória**. A persistência é atômica e a troca de referência é
atômica, cada uma por si. Depois do `rename` o arquivo já é o novo e não há
rollback de arquivo; existe uma janela de crash entre persistir e trocar, e a
recuperação é o próximo start ler o arquivo — que já passou por validação,
compilação, conexão e capability check antes de ser escrito.

D-055 registra as escolhas de implementação da Etapa 6 que a especificação não
fixava: o runtime candidato é construído do documento reparseado dos bytes que
serão persistidos; o callback de mutação e a leitura administrativa recebem
cópia profunda, nunca o documento do runtime publicado; e o plano administrativo
tem vocabulário próprio de erro.

D-056 registra as escolhas de implementação da Etapa 7: quatro categorias de
erro novas para as recusas de fronteira, cujos status a §3.3 fixa mas cujos
nomes a §10.2 não fornecia; a ordem entre as camadas de middleware; a contenção
da exceção por fora do Starlette; o `bind` na thread chamadora; a declaração dos
parâmetros de transformer no registry; e os contadores de `/status`. A revisão
da Etapa 7 aprovou D-056 como decisão de contrato.

D-057 registra as duas correções exigidas nessa revisão: o **snapshot
administrativo coerente** — revision, documento e política de uma única leitura
do runtime publicado, porque o par misturado quebraria o `expected_revision` da
Etapa 9 — e o **shutdown sem timeout**, em que `stop()` espera a thread HTTP até o
fim, a referência do servidor é adotada antes de `start()` e `_closing` impede
que uma aplicação em desmontagem volte a ser usada.

A Etapa 8 acrescentou `POST /admin/v1/config:validate`: valida o schema, compila
os transformers e a policy, e descarta o resultado — sem conectar, persistir,
alterar revision ou entrar na seção crítica. D-058 fixa o contrato (request na
raiz com schema HTTP próprio, resposta de quatro booleanos, `CONFIG_INVALID` para
falha de compilação) e a correção do `BodyLimitMiddleware`, que passou a cortar
em `413` autoritativamente porque a rota é a primeira com corpo sob o roteador do
FastAPI.

**Próximo passo: Etapa 9, somente após autorização.** Rotas de escrita e adoção
com backup; não foram antecipadas.

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

Fases 1 a 6.1 concluídas. Fase 7 em andamento, Etapas 1–9 concluídas; Etapa 10
(`AdminAudit`) não iniciada. Estado validado contra PostgreSQL 16.15 real, com a
suíte inteira: 2121 testes coletados, 2111 aprovados e 10 pulados por condição de
plataforma, sem nenhum deselect. Com `-m integration`, 486 selecionados (485
aprovados e 1 pulado por condição de plataforma), nenhum skip por falta de DSN.
Neste host Windows o pytest precisa de pilha de thread
ampliada (64 MiB) por causa de um teste adversarial da Fase 6; é ajuste de
ambiente, não correção de produto. Detalhes em `docs/HANDOFF.md`, seções 6
e 11.
