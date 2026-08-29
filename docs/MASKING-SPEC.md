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
EXCEPTION MATCH   -> ORIGINAL
MASKING MATCH     -> TRANSFORMER
NO MATCH          -> ORIGINAL
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

Quando `origin_name` não é determinável (expressões, funções, casts), o
matching usa apenas `output_name`.

## Exceptions

Exceptions possuem prioridade absoluta e são avaliadas contra os mesmos dois
nomes. Se `output_name` ou `origin_name` casar uma exception, o valor passa
original — mesmo que a regra de masking também casasse.

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
