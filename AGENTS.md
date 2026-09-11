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

As Etapas 1–3 foram revisadas, aprovadas e publicadas sem emenda. Esta rodada
autoriza exclusivamente a **Etapa 4: rotas UI, autenticação, origem exata,
headers e transporte mínimo para testes reais**, conforme `docs/PHASE-8-SPEC.md`.
Somente os quatro recursos previstos; três públicos e apresentação com bearer.
UI desligada preserva a Fase 7. Nenhuma sessão, tela autenticada, polling,
máquina de estados, CRUD ou escrita de configuração pela UI está autorizada.
Os testes reais usam os três browsers fixados e PostgreSQL 16 real.
A Etapa 4 está concluída; seus gates foram registrados em
`docs/PHASE-8-STAGE-4-VALIDATION.md`. As Etapas 5–9 e o push do commit local
da Etapa 4 exigem nova autorização.

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
