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

As Etapas 1–6 foram revisadas, aprovadas e publicadas sem emenda. Esta rodada
autoriza exclusivamente a **Etapa 7: adoção legada, validação explícita e CRUD
granular de regras e exceptions**, conforme `docs/PHASE-8-SPEC.md`.
Token somente em closure privada do transporte; dados e apresentação somente
em memória; logout/401/pagehide/pageshow/BFCache limpam tudo. Nenhuma chamada
administrativa antes do login. Cada escrita exige gesto explícito; conflitos
preservam o rascunho, sem retry, rebase ou rollback automático. Não implementar
reorder, edição de database/SQL, PUT /config ou itens das Etapas 8–9.
A fronteira HTTP da Etapa 4 permanece intacta. A Etapa 7 está concluída;
gates reais de componentes/browsers/PostgreSQL aprovados. Evidência em
`docs/PHASE-8-STAGE-7-VALIDATION.md`. Não publicar seu commit local nem iniciar
a Etapa 8 sem nova revisão e autorização.

Interfaces genéricas, editor ou execução de SQL, resultados do banco, funções
de DBA, auditoria consultável, front-end para MCP e expansões não previstas
continuam fora do escopo. Nenhum bind externo, TLS, proxy, deployment ou
serviço externo é autorizado pela Fase 8.

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
