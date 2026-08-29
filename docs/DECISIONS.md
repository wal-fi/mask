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

## D-011 — Valores nao-string sao convertidos com `str()`

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
