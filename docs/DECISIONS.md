# Decisions

Decisoes tomadas durante a implementacao que nao estavam especificadas nos
documentos. Criterio aplicado: a alternativa mais simples e segura compativel
com `CLAUDE.md` e `docs/`.

---

## D-001 — Layout de pacotes: `src/maskgw/`

O repositorio ja usa `config/` na raiz para o `masking.yaml`. Um pacote Python
`config/` na raiz colidiria com esse diretorio de dados.

Decisao: codigo em `src/maskgw/`, com os modulos de `docs/ARCHITECTURE.md`
como subpacotes (`maskgw.config`, `maskgw.masking`, e futuramente `maskgw.db`,
`maskgw.sql`, `maskgw.mcp`, `maskgw.gateway`, `maskgw.audit`).

Sem instalacao editavel: `pythonpath = ["src"]` no pytest.

## D-002 — Nome da variavel de ambiente da chave HMAC

`MASKGW_HMAC_KEY`. Nome fixo no codigo, nao configuravel pelo YAML — um
parametro do tipo `key_env` permitiria ao autor da configuracao apontar para
outra variavel, ampliando a superficie sem beneficio.

## D-003 — `regex` sem correspondencia devolve `[REDACTED]`

`re.sub` devolve o texto original quando o padrao nao casa. Isso seria um
vazamento silencioso: um e-mail fora do formato esperado sairia em claro.

Decisao: `count == 0` produz `[REDACTED]`. Falhar redigido, nunca em claro.
Vale tambem para erro inesperado de substituicao.

## D-004 — Conflito entre regras: vence a primeira do arquivo

Quando mais de uma regra de masking casa a mesma coluna, aplica-se a que
aparece primeiro no `masking.yaml`. Ordem explicita e previsivel, sem
heuristica de especificidade.

Exceptions continuam com prioridade absoluta sobre qualquer regra,
independentemente da posicao no arquivo.

## D-005 — `random` usa `secrets`, nao `random`

Gerador criptografico, sem estado global previsivel e sem semente que possa ser
inferida a partir de saidas anteriores.

## D-006 — Chave HMAC: minimo 32 caracteres

Segredo curto derrota o proposito do HMAC. Chave ausente, vazia, so com
espacos ou menor que 32 caracteres impede a inicializacao.

Espacos nas bordas sao removidos antes da validacao — evita o erro comum de
variavel de ambiente com quebra de linha.

## D-007 — `hmac_sha256` nao aceita nenhum parametro

Qualquer `config` em uma regra `hmac_sha256` e erro fatal. Garante que a chave
nao possa chegar pelo YAML por nenhum caminho.

## D-008 — Lista global de parametros proibidos

`key`, `secret`, `hmac_key`, `password`, `token`, `salt`, `pepper` e similares
sao recusados no `config` de QUALQUER transformer, nao so do HMAC. A mensagem
de erro cita o nome do parametro, nunca o valor.

## D-009 — `random` exige `strategy` explicita

Sem default de estrategia: `strategy` e obrigatorio. `length` e obrigatorio
quando `preserve_length: false` e proibido quando `preserve_length: true`
(combinacao ambigua). `preserve_length` tem default `true`.

Consequencia: `config/masking.yaml` foi atualizado — a regra `telefone` agora
declara `strategy: digits`.

## D-010 — `truncate` nao adiciona sufixo

`truncate` devolve `value[:length]`, sem reticencias nem marcador. O
transformer preserva um prefixo do dado original por definicao; e reducao de
exposicao, nao anonimizacao.

## D-011 — Valores nao-string sao convertidos antes da transformacao

> **Emendada na Fase 2 por D-015.** A conversao continua existindo, mas deixou
> de ser `str()`.

`MASKING-SPEC.md` estabelece que a saida pode ser string neste MVP. Valores
nao-nulos que nao sejam `str` sao convertidos antes da transformacao. NULL
nunca e convertido: permanece `None`.

Colunas sem correspondencia preservam o tipo original — nao passam por
conversao alguma.

## D-012 — Fase 1 nao registra log

Nenhum modulo importa `logging`. O componente `audit/` entra na Fase 5, com
log estruturado apenas de metadata. Ate la, a ausencia de log e verificada por
teste (`tests/test_leakage.py`).

## D-013 — Transformers nao expoem atributo `name`

A fonte da verdade do nome de um transformer e a chave do registry, propagada
para `MaskingRule.transformer_name`. Um `name` no proprio transformer seria
uma segunda fonte, passivel de divergir.

## D-014 — Riscos de configuracao: documentar, nao bloquear

A revisao de seguranca da Fase 1 confirmou quatro formas de o `masking.yaml`
anular a protecao. Nenhuma e defeito do engine: em todas o pipeline se comporta
como especificado.

| # | Risco | Efeito |
|---|---|---|
| H-1 | Exception larga (`mode` default e `contains`) | Desliga a regra inteira em silencio |
| H-2 | `regex` com replacement identidade (`(.*)` -> `\1`) | Devolve o valor original |
| H-3 | `truncate` com `length` >= tamanho do valor | Devolve o valor original |
| H-4 | `random` com `preserve_length: true` | Publica o comprimento do original |

Decisao: **documentar e fixar em teste**, nao bloquear no loader.

Motivo: a deteccao generica de "transformer inocuo" nao e decidivel — um
`truncate` longo pode ser legitimo em coluna de texto, e uma exception larga
pode ser intencional. Bloquear geraria falso positivo em configuracao valida.

Os quatro casos estao cobertos por `tests/test_config_hazards.py`, que fixa o
comportamento atual. Validacao no boot (avisar quando o padrao de uma exception
for substring do padrao de uma regra) fica registrada em
`docs/FUTURE-HARDENING.md`.

---

# Fase 2 — PostgreSQL Adapter + ResultSet Masking

## D-015 — Canonicalizacao explicita, nunca `str()`, com falha fechada

Emenda D-011. `str()` servia enquanto a Fase 1 so via valores de teste; contra
um banco real ele produz saida errada em dois casos concretos:

| valor do psycopg | `str()` | problema |
|---|---|---|
| `memoryview` de `bytea` | `<memory at 0x10f2a3040>` | embute o **endereco do objeto**: muda a cada execucao |
| `dict` de `jsonb` | `{'cpf': '...'}` | repr de Python: aspas simples e ordem de insercao |

O primeiro caso e o grave. `hmac_sha256`, `md5`, `sha256` e `sha512` sao
documentados como deterministicos; com `str(memoryview)` a mesma linha
produziria hashes diferentes entre consultas, **em silencio**.

Decisao: `maskgw.masking.canonical.canonicalize` define uma forma canonica por
tipo, e `Transformer.apply` passa a usa-la.

| tipo | forma canonica | observacao |
|---|---|---|
| `str` | o proprio valor | |
| `bool` | `true` / `false` | testado ANTES de `int`: `bool` e subclasse de `int` |
| `int` | `str(int)` | |
| `float` | `repr(float)` | forma curta com round-trip garantido |
| `Decimal` | `str(Decimal)` | preserva a escala do PostgreSQL: `1.10` nao vira `1.1` |
| `bytes`, `bytearray`, `memoryview` | base64 padrao | sem perda e sem endereco |
| `datetime` | ISO 8601 | testado ANTES de `date`: `datetime` e subclasse de `date` |
| `date`, `time` | ISO 8601 | |
| `UUID` | `str(UUID)` | minusculas, com hifens |
| `dict`, `list` | JSON canonico | `sort_keys=True`, separadores `,` e `:`, UTF-8 preservado |

Escalares dentro de JSON usam a mesma tabela, por `default=` do `json.dumps`.

**Qualquer outro tipo FALHA FECHADA**: `TransformerError`, nunca `str(obj)`. Um
`interval` do PostgreSQL chega como `timedelta` e derruba a consulta em vez de
gerar saida arbitraria. `NaN`/`Infinity` dentro de estrutura JSON tambem falham
fechado, porque JSON canonico nao os representa.

A mensagem de erro cita apenas o **nome do tipo**, nunca o valor. E a mensagem
do `json` (que embute o repr do objeto ofensor) e descartada, nao propagada.

O modulo vive em `masking/` porque quem precisa dele e `Transformer.apply`.
Depende so da stdlib, entao a pureza do nucleo continua valendo.

Coluna **sem** transformacao nao passa por nada disso: preserva exatamente o
objeto Python do psycopg. `Decimal` continua `Decimal`, `datetime` continua
`datetime`, JSONB continua `dict`, `bytes` continuam `bytes`.

## D-016 — Transacao: `autocommit`, e rollback defensivo

O adapter nao pode deixar a sessao `idle in transaction` — conexao presa
segura recursos e bloqueia manutencao no banco.

Alternativas descartadas:

- `with connection.transaction():` — o psycopg faz **COMMIT** ao sair sem erro.
  Commitar como mecanismo de limpeza foi vetado.
- `rollback()` incondicional ao fim de toda consulta — trabalho inutil e uma
  ida ao servidor por consulta, ja que em autocommit nao ha transacao aberta.

Decisao: a conexao e aberta com `autocommit=True`. Cada statement roda na sua
propria transacao implicita, que o servidor encerra ao termino — em sucesso ou
em erro. Nao ha COMMIT de operacao arbitraria, e a sessao volta a `idle`
sozinha, inclusive depois de um erro (o que mantem a conexao reutilizavel).

Como rede de seguranca, `_settle()` roda em `finally` apos toda consulta: se o
`transaction_status` nao for `IDLE`, faz **rollback**, nunca commit. Se o
proprio rollback falhar, a conexao e fechada em vez de propagar detalhe do
driver — `_settle` roda em `finally` e nao pode substituir o erro original.

`autocommit=True` e compativel com o enforcement read-only da Fase 4
(`default_transaction_read_only` / role sem privilegio de escrita).

Verificado contra PostgreSQL real por `pg_stat_activity`, de uma segunda
conexao, apos consulta bem-sucedida, apos erro do servidor e apos falha de
canonicalizacao.

## D-017 — O erro sanitizado e levantado FORA do bloco `except`

Descoberto por teste durante a Fase 2, e nao previsto no plano.

`raise DatabaseError(...) from None` zera `__cause__` e liga
`__suppress_context__`, o que basta para o traceback padrao do Python. Mas o
interpretador ainda pendura a excecao original em `__context__` quando o
`raise` acontece dentro de um handler ativo.

Consequencia: `error.__context__` continuava sendo o `psycopg.Error` cru, com
a mensagem do servidor — que pode conter valores, como em
`invalid input syntax for type integer: "12345678901"`. Qualquer formatador,
logger estruturado ou coletor de erros que percorra a cadeia de excecoes
exporia o dado. Com o `audit/` da Fase 5 isso deixaria de ser hipotetico.

Decisao: o adapter guarda o erro sanitizado numa variavel, sai do handler, e so
entao levanta, por `_raise_sanitized`. Fora do handler nao ha excecao corrente,
entao `__cause__` e `__context__` ficam ambos `None`.

Fixado por teste que percorre as duas cadeias e por outro que renderiza o
traceback completo.

## D-018 — Leitura em lotes com `fetchmany`

O adapter le o result set em lotes de `DEFAULT_BATCH_SIZE` (500) linhas e
mascara lote a lote, em vez de `fetchall()`.

**Nao e row limiting** — que e da Fase 4. Nenhuma linha e descartada e nao ha
sinalizacao de truncamento: e apenas a estrategia de consumo, escolhida para
que o limite da Fase 4 entre sem reescrever o adapter.

O gerador que produz os lotes e privado e consumido inteiramente dentro de
`execute`: linha crua nao escapa da funcao.

## D-019 — SQLSTATE classifica, mas nao viaja

A mensagem devolvida ao chamador vem de uma tabela fixa, indexada pela classe
do SQLSTATE (os dois primeiros caracteres). O codigo em si **nao** entra na
mensagem: `42P01` viraria um oraculo barato de existencia de tabela e coluna.

Nada mais da excecao original sai: nem `str(exc)`, nem `repr(exc)`, nem `diag`,
nem query, nem parametros. O `DatabaseError` resultante tambem nao carrega
atributo algum do erro de origem.
