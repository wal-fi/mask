# Fábrica privada de api na composição pinada — desenho

Estado (V3, 2026-11-03): testes congelados `d6b15ac1…` (16379 bytes, 29
casos; RED medido pelo root: 29 coletados, 29 falhas, todas `TypeError` pela
palavra-chave ausente, 2,487 s); os 63 testes `a3ebf78b` intactos. O delta
da seção 1 foi aplicado só em
`docs/poc/pg16_shell_native_control_collect_pinned.py`, substituindo a
revisão `109ab960` (preservada pelo root como dado e no Git). Implementação
inteiramente simulada; nenhuma fábrica nativa foi criada ou chamada; o
programador não executou testes. Revisão final do root: fonte37b098cf/
5373bytes,29próprios e748relacionados aprovados com fakes. Evidências e
limites em [validação](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-FACTORY-VALIDATION.md).
O texto abaixo é o desenho histórico escrito antes da implementação.

Data: 2026-11-03. Sob a delegação geral vigente (trabalho rotineiro autônomo,
com as proibições explícitas e as permissões efetivas das ferramentas
valendo); decisão técnica do root, não aprovação individual do usuário.
Programador Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
`claude-opus-5-5`, esforço `medium`. Nesta etapa existem só este desenho,
`tests/test_pg16_shell_native_control_collect_factory.py` e a seção 10 do
PROCEDURE; nenhuma implementação Python mudou e nenhum teste foi executado
pelo programador.

Lido nesta etapa (fonte real, não memória): composição
`docs/poc/pg16_shell_native_control_collect_pinned.py` (revisão aceita
`109ab960`, 4291 bytes), início dos 63 testes pinados, construtor de
`_Win32Backend`, PROCEDURE e o registro da identidade no CHECKPOINT.

## 1. Delta mínimo (a aplicar depois do RED e da revisão)

Só a composição muda, de forma aditiva; a revisão `109ab960` será
explicitamente substituída apenas nesse arquivo e preservada como dado e no
Git. Coletor `1972ec74`, backend `ccb3f74a`, verificador `b375`, entrada
`356d`, orquestrador `b419`, adaptador `eaeb`, backend de controle `10c9`,
chamador `dfcc` e estado16 ficam fixos. Os 63 testes antigos não mudam.

Assinatura: `_collect_pinned(collector_src, backend_src, api, nonce, argv0,
*, api_factory=None)`.

Ordem:

1. Pins das duas fontes (tipo `bytes` exato, tamanho, SHA) antes de qualquer
   `exec` e antes da fábrica ⇒ `COLLECT_SOURCE`, sem consumir.
2. `api_factory` não `None` e (`api` não `None` ou não chamável) ⇒
   `("INVALID", "COLLECT_ARGUMENT", None, None)`, sem `exec`, fábrica ou
   consumo.
3. `api is None and api_factory is None` ⇒ `COLLECT_UNAVAILABLE`, sem consumo.
4. Tentativa consumida ⇒ `COLLECT_POISONED`, sem chamar a fábrica.
5. Registro `_Attempt` publicado em `_ATTEMPTS` antes de qualquer `exec`, com
   os campos novos `factory` (a referência original) e `factory_started`
   (`False`).
6. `exec` do coletor e do backend, como hoje.
7. Com fábrica: `factory_started = True` **antes** da chamada (nunca
   desfeito); `returned = api_factory(record.native)`, o mesmo dict já
   executado, uma única vez; `record.api = returned` antes do construtor.
   `returned is None` ⇒ `COLLECT_UNAVAILABLE` com tentativa consumida, sem
   construtor nem efeito da política.
8. `_Win32Backend(record.api, record.collector)`, troca do seam copiado e
   `collect`, como hoje. Ledgers originais nunca substituídos.

`api` retornada malformada ou falha comum da fábrica ⇒ `COLLECT_INTERNAL`,
com registro, fábrica e namespaces retidos. Controle propaga com a mesma
identidade; chamada seguinte bloqueada. Chamada reentrante vinda da fábrica
encontra `_ATTEMPTS` não vazio ⇒ `COLLECT_POISONED`. Sem fallback; a
composição não referencia nem chama `_load_native`.

## 2. Limites

A fábrica é um seam privado, não fronteira de autenticação. Um callback pode
ter efeitos arbitrários: nada aqui os autoriza, e os testes só usam fakes
Python que devolvem a api falsa. Mesmo namespace e identidade dos tipos
`ctypes` **declarados** (`OBJECT_ATTRIBUTES`, `IO_STATUS_BLOCK`,
`PROTOTYPES`) são conferidos; nenhum trampolim `ctypes`, DLL ou conversão de
chamada nativa é exercitado, e nada prova limpeza nativa.

## 3. Testes (antes do código; baseline esperado: `TypeError` pela palavra-chave ausente)

29 casos previstos, contagem a medir pelo root: fontes adulteradas
(2 × 4) sem chamar a fábrica; fábrica não chamável (4) e `api`+fábrica (1)
⇒ `COLLECT_ARGUMENT` sem `exec`; ausência de ambos sem consumo; caminho
legado com `api_factory=None`; tentativa consumida sem chamar a fábrica;
aprovado/rejeitado pela fábrica com o mesmo namespace, chamada única, latch
antes da chamada, construtor com a api retornada e tipos declarados; retorno
`None`; api malformada (3); falha comum com sentinela fora de tupla, `repr` e
saída; controle durante, antes (no 2º `compile`), antes de qualquer `exec`
e depois da fábrica (api retornada que interrompe); chamada reentrante;
fechamento incerto retido. Os auxiliares vêm dos 63 testes por `runpy`; os
efeitos ficam bloqueados no exercício pelo mesmo `sealed`.
