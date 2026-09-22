# AI Data Masking Gateway

Você é o principal engenheiro responsável por desenvolver este projeto.

O sistema é um Gateway MCP entre uma IA e bancos de dados.

Fluxo:
IA → MCP → Gateway → Database → Result Set → Masking Engine → MCP → IA

## Objetivo
Permitir que IAs consultem bancos de dados sem expor dados sensíveis.

## Escopo atual
- MCP Server
- PostgreSQL
- SELECT read-only
- Masking Engine
- regras globais
- matching case-insensitive
- matching por contains
- exceptions
- transformers extensíveis
- configuração externa
- testes automatizados

Não implementar agora: CI/CD, RBAC complexo, interfaces genéricas, gerenciamento de schema, migrations, MySQL ou funcionalidades de DBA.

### Exceção aprovada — Fase 8

A partir da aprovação de 2026-09-09, somente a UI administrativa **local,
opt-in e estritamente delimitada por `docs/PHASE-8-SPEC.md`** está autorizada
como escopo de front-end. A especificação foi aprovada integralmente, incluindo
as quatro decisões da seção 8 (D-061 a D-064 em `docs/DECISIONS.md`).

As Etapas 1–9 foram revisadas e aprovadas; a publicação final da Etapa 9 está
autorizada. As Etapas 1–8 foram publicadas sem emenda. A **Etapa 9:
pacote instalado, revisão adversarial final e fechamento dos critérios de aceite**
foi concluída, com todos os gates aprovados. A Fase 8 está concluída conforme
`docs/PHASE-8-SPEC.md`, com os limites documentados na evidência.
Nenhuma funcionalidade, rota, modelo, permissão ou dependência foi ampliada.
Preservar memória volátil, uma escrita pendente, gestos explícitos e ausência
de retry/rebase/fila/rollback automático. A Fase 9 foi autorizada em
2026-09-22 **somente para sua Etapa 1 documental**: especificação, threat model,
decisões e rastreabilidade do listener PostgreSQL, múltiplos datasources e
Admin UX v2. A Etapa 1 foi concluída e aprovada; nenhuma implementação funcional
das Etapas 2–12 está autorizada sem revisão e autorização próprias.
Evidência: `docs/PHASE-8-STAGE-9-VALIDATION.md`.

Interfaces genéricas, editor SQL administrativo, resultados do banco na UI,
funções de DBA, auditoria consultável e front-end para MCP continuam fora do
escopo. Bind PostgreSQL, TLS, façade PGWire, catálogo multi-datasource e
redesign administrativo são contratos exclusivos da Fase 9; continuam sem
implementação até a autorização da etapa correspondente.

## Matching
Por padrão: case-insensitive + substring/contains.

Regra `cpf` deve corresponder a `cpf`, `CPF`, `num_cpf`, `tipo_cpf`, `cliente_cpf`, `cpf_cliente` etc.

## Exceptions
Exceptions têm prioridade sobre masking.

Ordem:
EXCEPTION → MASKING RULE → ORIGINAL VALUE

## Segurança
- O cliente MCP/IA é não confiável.
- O dado original nunca pode chegar ao cliente sem passar pelo Masking Engine.
- Nunca registrar dados sensíveis em logs ou erros.
- Nunca permitir que a IA altere ou desative regras.
- Apenas SELECT no MVP.
- A conexão do Gateway deve ser read-only.

## Desenvolvimento
Antes de mudanças importantes: entender arquitetura, consultar docs, analisar segurança, implementar, testar e revisar.

Security > correctness > performance > convenience.
