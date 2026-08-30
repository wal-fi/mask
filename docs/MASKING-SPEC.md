# Masking Specification

## Conceito

O Masking Engine recebe:
- `output_name` da coluna retornada
- `origin_name` da coluna de origem, quando determinável
- valor
- tipo da coluna
- regras configuradas

E retorna o valor transformado.

## Pipeline

```text
DERIVED (a AST provou dependência sensível)  -> TRANSFORMER
EXCEPTION MATCH (pelo nome autoritativo)     -> ORIGINAL
MASKING MATCH (output_name OU origin_name)   -> TRANSFORMER
NO MATCH                                     -> ORIGINAL
```

Default do MVP: **ALLOW**. Coluna sem correspondência passa normalmente.

## Matching

Default:
- case-insensitive
- substring/contains

Modos suportados: `contains` (default) e `exact`.

Exemplo de regra: `cpf`

Matches:
- cpf
- CPF
- Cpf
- num_cpf
- tipo_cpf
- cod_cpf
- cliente_cpf
- cpf_cliente
- nr_cpf

### Dois nomes

O matching é avaliado contra `output_name` **e** `origin_name`.
A regra é aplicada se qualquer um dos dois corresponder.

```sql
SELECT cpf AS documento FROM cliente
```

| campo | valor | casa `cpf`? |
|---|---|---|
| output_name | documento | não |
| origin_name | cpf | sim |

Resultado: mascarado.

Quando `origin_name` não é determinável (expressões, funções, casts, UNION), o
matching usa `output_name` — e, desde a Fase 6.1, a **análise de sensitividade
por AST**, que identifica as colunas de que a expressão depende e aplica a
regra delas ao resultado. Ver `docs/DECISIONS.md` (D-043).

## Exceptions

Exceptions possuem prioridade absoluta sobre as regras de masking, mas são
avaliadas contra **um** nome: o **autoritativo** da coluna — `origin_name`
quando ele existe, `output_name` apenas quando não há origem determinável.

Isso é assimétrico em relação ao masking de propósito. O `output_name` é
escolhido pelo cliente: se a exception casasse por ele, toda exception
configurada seria uma forma de desmascarar qualquer coluna sensível
(`SELECT cpf AS tipo_cpf`). O alias pode **adicionar** proteção, nunca removê-la.

```sql
SELECT tipo_cpf FROM cliente             -- origem tipo_cpf  -> ORIGINAL
SELECT tipo_cpf AS documento FROM ...    -- origem tipo_cpf  -> ORIGINAL
SELECT cpf AS tipo_cpf FROM cliente      -- origem cpf       -> MASCARADO
```

O `mode` default de uma exception é `exact` — e não `contains`, como nas regras.
Uma exception larga continua possível, com `mode: contains` explícito no
arquivo. Ver D-042 e D-045.

Exemplo:

```yaml
masking:
  - match: cpf
    mode: contains
    transformer: md5

exceptions:
  - match: tipo_cpf
    mode: exact
```

Resultado:
- cpf → masked
- num_cpf → masked
- tipo_cpf → original

## Transformers

O transformer é responsável somente pela transformação.

Interface conceitual:

`transform(value, context) -> transformed_value`

Transformers do MVP:

| transformer | determinístico | observação |
|---|---|---|
| `md5` | sim | hash sem chave |
| `sha256` | sim | hash sem chave |
| `sha512` | sim | hash sem chave |
| `hmac_sha256` | sim | chave via secret/env |
| `regex` | sim | `pattern` + `replacement` |
| `random` | **não** | valor diferente a cada execução |
| `fixed` | sim | `value` constante |
| `truncate` | sim | `length` |

### Hashes sem chave

`md5`, `sha256` e `sha512` permanecem disponíveis porque o Gateway é um motor
genérico de transformação.

**Não são recomendados para pseudonimização de domínios pequenos.** CPF tem
cerca de 10^9 valores válidos: uma tabela reversa completa é construível em
tempo curto, e o mesmo vale para CNPJ, telefone e CEP. Para esses domínios use
`hmac_sha256`.

### HMAC-SHA256

A chave é lida **exclusivamente** de secret/variável de ambiente.

- nunca no `masking.yaml`
- nunca vinda do cliente MCP
- nunca registrada em log ou mensagem de erro

Se alguma regra usar `hmac_sha256` e a chave não estiver disponível no boot, o
processo **não inicia** (fail-closed).

### Random

`random` não é determinístico: a mesma linha produz valores diferentes entre
consultas. Isso quebra correlação e joins do lado do cliente. Use quando o
objetivo for descaracterizar, não pseudonimizar.

## NULL

NULL permanece NULL. Nenhum transformer é aplicado sobre NULL.

## Determinismo

Hashes e HMAC são determinísticos: o mesmo valor de entrada produz sempre a
mesma saída dentro da mesma configuração e chave.

## Extensibilidade

Adicionar um transformer não deve exigir alteração no núcleo do Masking Engine.
Transformers customizados definidos em Python pelo usuário estão fora do MVP.

## Configuração

Carregada uma vez no boot, validada com Pydantic, imutável em runtime.
Erro de schema, transformer inexistente, regex inválida ou parâmetro ausente
impedem a inicialização.

O cliente MCP não pode ler, alterar ou desabilitar regras.

## Expressões derivadas

Uma expressão sobre coluna sensível não tem origem no protocolo do PostgreSQL.
A análise da AST resolve o caso: para cada posição do result set, ela reúne as
colunas referenciadas e determina a regra que as cobre.

```sql
SELECT substr(cpf, 1, 11) AS documento FROM cliente
-- depende de `cpf` -> o resultado da expressão recebe o transformer de `cpf`
```

Regras:

- o transformer é aplicado ao **resultado da expressão**, não à coluna de
  origem. Não se tenta reconstruir o valor original.
- em um UNION, basta um ramo ter dependência sensível para a posição inteira
  ser sensível.
- duas regras **diferentes** na mesma posição (`concat(cpf, email)`) fazem a
  consulta ser **rejeitada**: não há transformer único comprovável.
- serialização de linha inteira (`row_to_json(c)`) é **rejeitada**: não há
  referência por campo para provar nada.
- a análise respeita exceptions sobre o nome referenciado:
  `substr(tipo_cpf, 1, 3)` continua original.
