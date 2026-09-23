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
Nenhuma funcionalidade, rota, modelo, permissão ou dependência da Fase 8 foi
ampliada. Preservar memória volátil, uma escrita pendente, gestos explícitos e
ausência de retry/rebase/fila/rollback automático. A Fase 9 foi autorizada em
2026-09-22 para sua Etapa 1 documental e para a Etapa 2 (modelos, store
cifrado/autenticado, validação de destino e migração explícita), e em
2026-09-23 para a Etapa 3: registry multi-datasource e lifecycle, ativados
somente pelo parâmetro interno `datasource_catalog` do composition root
(D-087–D-091). As Etapas 4–12 ainda exigem revisão e autorização próprias. Não
iniciar Admin API v2, UI v2, PGWire, variável de ambiente nova, extensão da
tool MCP ou qualquer etapa posterior.
Evidência: `docs/PHASE-8-STAGE-9-VALIDATION.md`.

Interfaces genéricas, editor SQL administrativo, resultados do banco na UI,
funções de DBA, auditoria consultável e front-end para MCP continuam fora do
escopo. Bind PostgreSQL, TLS, façade PGWire, rotas v2, ativação do catálogo por
ambiente e redesign administrativo são contratos exclusivos das etapas
posteriores da Fase 9; continuam sem implementação.

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
