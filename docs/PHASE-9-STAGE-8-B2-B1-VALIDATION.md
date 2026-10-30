# Fase 9 — Etapa 8 — B2-B1: núcleo lógico de reservas

**Estado (2026-10-20): implementado e validado localmente no CPython 3.11.3;
revisão pelo Claude2 concluída, sem bloqueador no núcleo isolado.
Fechamento e D-112 aprovados explicitamente pelo usuário em 2026-10-20.
Sem integração, worker, SQL, pressão de memória, commit ou push.
Não fecha B-1 fim a fim, B-2 ou D-090 gate 2.**

## 1. Autoridade e checkpoint

O usuário respondeu **"sim"** ao pedido de implementar somente B2-B1:
controle lógico de reservas e testes determinísticos, com revisão pelo
Claude2, sem workers, SQL, pressão de memória ou commit/push. Fonte:
`PHASE-9-STAGE-8-B2-B-PLAN.md`; decisão D-112, com revisão técnica concluída
e aceite final do usuário em 2026-10-20, restrito ao núcleo isolado.
Não há aval aos gates posteriores ou a um contrato agregado alternativo.

Checkpoint: `master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`,
referência local `origin/master` em
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind, sem fetch.
Freeze próprio deste lote: **345 arquivos selecionados**, antes de mudanças;
separado dos freezes da preparação e do B2-A. Alterações locais anteriores,
arquivos pessoais não rastreados e `.venv` existente preservados.

## 2. Entrega e limites do modelo

- `src/maskgw/runtime/budget.py`: máquina de estados pura, stdlib apenas,
  sem lock próprio, I/O, processo, conexão, callback externo ou integração.
  Nenhum outro módulo de produção a importa e nenhum export foi adicionado.
- `tests/test_runtime_budget.py`: fixtures de créditos numéricos pequenos,
  sem alocação proporcional às cotas. Estados, ordens, capacidades, cleanup,
  tokens, gerações e falhas modeladas; sem threads ou testes de pressão.
- D-112 e documentos de estado: autorização estreita, implementação isolada
  e pendências. Os bloqueantes e resultados históricos continuam iguais.

O colaborador confiável informa os custos. A conta é base + cobranças de
geração/candidato/auxiliar + margem + worker/pai por sessão. Isso é apenas
contabilidade: não calcula custos reais nem impõe limite de memória.
Os cinco fatos de `CleanupConfirmation` também são declarados no modelo;
não autenticam worker nem comprovam término/fechamento de recursos reais.

São ordinais internos de datasource, não strings recebidas de cliente.
Capacidades são explícitas; limites de construção do modelo de 4.096 slots,
1.024 ordinais e inteiros de 63 bits não são novos defaults operacionais.
Nenhum caminho, ambiente, API, sessão real ou política passou a ter esse teto.

O núcleo exige **todas** as chamadas serializadas por coordenador externo.
Os testes enumeram ordens de transição, não provam concorrência do registry.
O `close()` e os locks do registry real continuam inalterados.

## 3. Invariantes exercitados

- Base e margem cobradas desde a criação; igualdade com o total aceita;
  excesso de um byte e falta independente de vaga/global/datasource/worker/
  slot/candidato/geração/auxiliar recusam sem mudar a imagem.
- Sessão reservada/ociosa e saída pendente mantêm toda a cobrança. Cada
  condição de cleanup ausente impede liberar vaga e créditos. Um job
  concluído não gera transição de liberação.
- Candidato vira geração sem abrir buraco na conta, incluindo substituição
  em duas linhas do estado e publicação pré-reservada durante shutdown.
  Geração antiga continua cobrada e suas sessões mantêm a referência.
- Retirar/reabilitar várias vezes mantém todas as gerações ainda presas;
  não presume limite de aposentadas como teto de memória. Descarte só
  devolve crédito numa segunda transição confirmada e sem referências vivas.
- Tokens de outra instância, campos inválidos, época antiga e slot reutilizado
  não devolvem crédito de outro dono. Época esgotada não volta a zero.
  Duplicar release da mesma época já vazia não cria crédito.
- Bookkeeping tem slots fixos, sem tombstones, aliases ou histórico de
  tentativas recusadas. Objetos de status e tokens são imutáveis; repr fixo.

## 4. Falhas modeladas, não garantia de OOM

Imagens novas são preparadas antes de publicação. As regressões injetam
falhas na construção do slot/estado e na escrita antes/depois da troca de
referência. Restauração normal mantém a imagem inteira, épocas e cobrança.
Isso inclui publicação de substituição, com candidato e geração antiga.

O par de imagens de fallback é preparado **antes** da troca. Se a restauração
falhar, uma só referência registra falha terminal e as duas imagens possíveis
para não perder o dono anterior de um release; cobra todo o total por quarentena,
recusa qualquer nova mutação e não reutiliza créditos. São no máximo duas
imagens retidas, não um histórico ilimitado. O custo real dessas estruturas
ainda depende da futura composição de `B`.

Erros são categoria e mensagem fixas, levantados fora do handler original,
sem exceção interna encadeada contendo canários. Python ainda pode anexar
uma exceção **já ativa no chamador** como `__context__`, suprimida por
`from None`; isso tem contraprova própria e não é atribuído ao núcleo.
Isso cobre os pontos injetados; não prova recuperação de toda falha arbitrária de CPython,
`BaseException`, allocator ou SO. Não foi produzida pressão real de memória.
Release de crédito é lógico, não prova de devolução de commit ao SO.

## 5. Medições desta rodada

Ambiente existente: Windows, **CPython 3.11.3**, sem recriar/instalar `.venv`.
Mypy executado nesse interpretador com dois alvos de linguagem; isso não é
execução nativa em 3.14 nem certificação POSIX.

1. Coleta inicial do novo arquivo: **309 casos**, antes da primeira execução.
   A primeira execução passou, exit 0; sumário suprimido pelo `-q` duplicado
   (configuração e CLI), contagem previamente coletada.
2. Revisão própria adicionou três casos antes da próxima execução: falha
   antes/depois do swap de substituição e falha de seu rollback. Nova coleta:
   **312 casos**, sem excluir ou enfraquecer os anteriores.
3. Execução combinada: **563 passed em 7,58 s**, zero falhas/skips:
   312 do núcleo + 201 do snapshot local + 50 de pureza/separação de planos.
   Nenhum teste de equivalência por processo ou de integração foi incluído.
4. `ruff check src tests`: aprovado; `ruff format --check src tests`:
   **231 arquivos** conformes.
5. `mypy --strict --python-version 3.11 src tests` e alvo `3.14`:
   **231 arquivos**, sem erros em ambos.

Durante a construção houve ajustes de lint/tipagem dos arquivos novos;
os gates acima são sobre os arquivos ajustados. Nenhuma configuração global
de lint/tipagem foi afrouxada. As duas supressões locais de mypy nos testes
são contraprovas deliberadas de escrita em objetos congelados.

Comando da execução combinada:

```powershell
.venv\Scripts\python.exe -B -m pytest -o addopts=--strict-markers -q tests/test_runtime_budget.py tests/test_runtime_snapshot.py tests/test_purity.py tests/test_plan_separation.py
```

Não foram executados suíte integral, PostgreSQL, Docker, browser, frontend,
build de pacote, prova de SO, pressão, CPython moderno nativo ou POSIX.
O gate novo é exclusivamente do núcleo isolado, não do produto operacional.

## 6. Revisão e regressões

Revisão somente leitura pelo Claude2, sessão
`8c17679e-87ce-4d9c-84f8-806d013fc4db`. Não executou testes nem alterou
arquivos. Não identificou perda de crédito/admissão, mas encontrou uma
ambiguidade média de API e cinco observações menores.

Dois casos foram escritos **antes** da correção e reproduziram os achados:
**2 failed, 312 deselected** na seleção `-k test_review`:

1. `False` significava tanto reserva ainda retida quanto já liberada;
2. repetir release incompleto numa reserva HELD tentava publicar uma imagem
   idêntica e podia levar a falha terminal desnecessária.

Corrigido com `ReleaseOutcome.RELEASED/HELD/ALREADY_RELEASED`, comparação
explícita obrigatória (coerção booleana levanta erro fixo) e no-op real para
HELD ainda não liberável. Não há chamador operacional a migrar.

Também tratados: publicação terminal em uma referência com os dois donos;
qualificação do contexto ativo do chamador; validação em uma passagem por
slots e outra pelos ordinais, sem produto datasources × slots; isolamento
por AST com contraprovas de imports absolutos/relativos.

Cobertura ampliada, sem descartar os casos anteriores: dez mutações recusadas
em instância terminal, ambas as imagens de quarentena antes/depois de write,
duas linhas da substituição, época máxima/parcial, sessão admitida que inicia
após retirada da geração, estados inválidos de publish, recusas após a
barreira e 12 ordens de publish/admissão/shutdown em dois datasources.

Nova coleta **366 casos**, antes da execução. Rodada combinada intermediária:
**617 passed em 6,95 s**, zero falhas/skips (366 + 201 + 50).
Os 309/312 passes anteriores e os dois vermelhos de regressão ficam preservados,
não substituídos retroativamente.

Na rerevisão, Claude2 confirmou F1–F6 resolvidos e a contagem de 366 casos
por leitura, sem executar testes ou presumir resultados finais. Não apontou
bloqueador no núcleo lógico isolado. Permaneceram observações menores:
checagem de imports dinâmicos literais, confirmação do retorno do no-op,
`TypeError` deliberado fora da família `BudgetError`, e ordens de descarte
intercalado com publicação/fechamento.

Depois da rerevisão, sem mudar `budget.py`, foram reforçados os testes:
AST complementada por busca literal do caminho do módulo, retorno HELD
explicitamente conferido no no-op e seis ordens de retirada/descarte/
publicação/shutdown. Import calculado/reflexivo não é certificado ausente
só por esses testes; a preservação do código operacional é conferida por hash.
O `TypeError` da coerção booleana ficou documentado em D-112. Os seis casos
adicionais foram executados pelo implementador, não pelo revisor.

## 7. Gates finais e preservação

Coleta final **372 casos**, antes da execução; nenhum caso anterior removido.
Execução combinada final sobre os arquivos entregues:

- **623 passed em 5,85 s**, zero falhas/skips: 372 do núcleo, 201 do
  snapshot local e 50 de pureza/separação de planos;
- Ruff check e format check de `src tests`: aprovados, **231 arquivos**;
- mypy strict de `src tests`, alvos **3.11 e 3.14**: aprovados, **231 arquivos**
  em cada alvo; execução das ferramentas no CPython 3.11.3 existente.

SHA-256 dos arquivos finais:

- `src/maskgw/runtime/budget.py`: `fc37d6443221fd2bc54548c4d30f4af6c4b686a262f51eaca4586ca10ef2d5da`;
- `tests/test_runtime_budget.py`: `0e972ea220426d0b0d9088535c109410d94ad1e2ac479f3cef380eb046063673`.

Contra o freeze de **345 arquivos selecionados deste lote**, somente oito
documentos existentes alterados e três arquivos adicionados: módulo, testes
e esta evidência. Nenhuma remoção ou alteração em outro código/teste/recurso,
dependência, `.venv/pyvenv.cfg` ou evidência histórica B2-A. O relatório antigo
e os fontes/sumário arquivados do diagnóstico B2-A foram preservados.
`git diff --check`, UTF-8 estrito e whitespace conferidos. Depois dos gates
só documentos mudaram; por isso não se repetiu a suíte para o fechamento.

HEAD e referência local `origin/master` permanecem os do checkpoint, 1 ahead/
0 behind, sem fetch, stage, commit, emenda ou push. Working tree anterior e
arquivos pessoais preservados. O usuário aprovou o fechamento em 2026-10-20,
com o limite da §8; isso não aprova nenhum gate posterior nem produção.

Os gates de produto de memória, admissão/locks reais, worker, fetch/pipeline
e B-1 fim a fim ficam separados. B-2 e D-090 gate 2 permanecem abertos;
SQL PGWire segue recusada com `0A000`.

## 8. Aprovação do fechamento

Em 2026-10-20, após a entrega revisada e a apresentação dos resultados, o
usuário respondeu **"aprovado"**. O aval fecha somente o lote B2-B1 e a
D-112 do núcleo lógico isolado, com todos os limites e resultados desta
evidência preservados. Não é aprovação de contenção real, integração ou
aceitação de B-2/D-090 como risco.

Este registro altera somente documentos de estado, decisão e evidência.
Código, testes, recursos e medições não mudaram; nenhuma suíte foi repetida.
Sem commit, push, SQL, worker, pressão de memória ou autorização de próximo
lote. B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.
