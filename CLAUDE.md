# AI Data Masking Gateway

Você é o principal engenheiro responsável por desenvolver este projeto.

O sistema é um Gateway MCP entre uma IA e bancos de dados.

Fluxo:
IA → MCP → Gateway → Database → Result Set → Masking Engine → MCP → IA

## Objetivo
Permitir que IAs consultem bancos de dados sem expor dados sensíveis.

O objetivo é um Data Masking Gateway simples, não uma plataforma de DLP ou de data access governance.

## Stack
Python, psycopg3, pglast, Pydantic, YAML, pytest.

## Escopo atual
- MCP Server
- PostgreSQL
- SELECT read-only
- Masking Engine
- regras globais
- matching case-insensitive
- matching por contains
- matching por output_name e origin_name
- exceptions
- transformers extensíveis
- configuração externa
- testes automatizados

Não implementar agora: CI/CD, RBAC, interface web, gerenciamento de schema, migrations, MySQL, funcionalidades de DBA, bloqueio de WHERE/ORDER BY/GROUP BY sobre dados sensíveis, supressão de agregações, controle de cardinalidade, column-level GRANT automático, JSONB deep inspection, transformers Python customizados e multi-tenant.

Ver `docs/FUTURE-HARDENING.md`.

## Matching
Por padrão: case-insensitive + substring/contains.

Regra `cpf` deve corresponder a `cpf`, `CPF`, `num_cpf`, `tipo_cpf`, `cliente_cpf`, `cpf_cliente` etc.

O matching é avaliado contra `output_name` e `origin_name`. A regra é aplicada se qualquer um dos dois corresponder. Isso impede bypass por alias: `SELECT cpf AS documento` continua mascarado.

Quando a proveniência não é determinável, usa-se apenas `output_name`.

## Exceptions
Exceptions têm prioridade sobre masking e são avaliadas contra os dois nomes.

Ordem:
EXCEPTION → ORIGINAL
MASKING MATCH → TRANSFORMER
NO MATCH → ORIGINAL

O default é ALLOW: coluna sem correspondência passa normalmente. Não usar default deny neste MVP.

## Segurança
- O cliente MCP/IA é não confiável.
- O dado original nunca pode chegar ao cliente sem passar pelo Masking Engine.
- Nunca registrar dados sensíveis em logs ou erros.
- Nunca permitir que a IA altere ou desative regras.
- Apenas SELECT no MVP.
- A conexão do Gateway deve ser read-only.
- `statement_timeout` e limite máximo de linhas são obrigatórios.
- Configuração fail-closed: config inválida impede a inicialização.
- Erros do PostgreSQL sanitizados; mensagem bruta nunca chega ao cliente.
- A chave do HMAC vem de secret/env, nunca do `masking.yaml`, nunca do cliente.

## Desenvolvimento
Antes de mudanças importantes: entender arquitetura, consultar docs, analisar segurança, implementar, testar e revisar.

O plano de implementação está em `docs/ROADMAP.md`. Não avançar de fase sem aprovação, nem com teste falhando.

Security > correctness > performance > convenience.
