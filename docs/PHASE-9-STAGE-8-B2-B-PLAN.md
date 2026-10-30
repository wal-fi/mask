# Fase 9 — Etapa 8 — B2-B: contenção, admissão e orçamento global

**Estado (2026-10-20): preparação documental autorizada pelo usuário;
proposta revisada pelo Claude2. Depois, autorizado somente B2-B1, núcleo
lógico e testes isolados (§11), implementado localmente e revisado
tecnicamente sem bloqueador no núcleo isolado; fechamento e D-112 aprovados
pelo usuário em 2026-10-20, sem ampliar a autorização.
Nenhum teste de pressão, integração ou novo harness autorizado por este plano.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos; SQL PGWire continua
recusada com `0A000`. Sem commit/push ou liberação de produção.**

## 1. Autoridade e fatos preservados

Depois de aprovar o registro B2-A, o usuário respondeu **"pode"** à proposta
de preparar com o Claude2 o próximo lote de contenção e orçamento global de
memória, **ainda sem implementação**. Isso permite escrever e revisar esta
proposta, não aprovar suas escolhas ou executar seus lotes.

Checkpoint: `master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`,
referência local `origin/master` em
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind, sem fetch.
Working tree anterior preservado, incluindo alterações de código e testes
dos lotes anteriores, arquivos não rastreados e `.venv` existente.

Fontes locais: desenho aprovado, §§3–4 e 10.3–10.5 de
`PHASE-9-STAGE-8-DESIGN.md`; plano anterior
`PHASE-9-STAGE-8-B2-PLAN.md`; diagnóstico
`PHASE-9-STAGE-8-B2-A-VALIDATION.md`, cujo **registro**, não contenção, foi
aprovado em 2026-10-19.

- B2-A: seis controles e 36 casos concluídos, cleanup confirmado. Os 12
  job-only excederam 32 MiB; os 24 com cota individual ativa respeitaram os
  caps **somente nos perfis medidos**, com um membro por vez.
- Job herdado do host presente, restrições desconhecidas. Não se contorna
  essa restrição nem se atribui a proteção exclusivamente ao job próprio.
- FAIL histórico agregado de 384 MiB permanece FAIL, sem tolerância,
  subtração de baseline ou substituição retroativa por reserva lógica.
- Não há prova operacional de memória do pai, codec, ledger global,
  múltiplos workers ou fetch/proveniência/transação/masking integrados.

## 2. Menor próximo lote recomendado: B2-B1, núcleo lógico isolado

Propor para autorização separada apenas um **núcleo puro de contabilidade e
lifecycle**, com testes determinísticos de estado e de ordens de transição. Não criar
worker, launcher, Job Object, processo de pressão ou conexão. Não importar
esse núcleo no composition root, registry, listener ou caminho de consultas.

O núcleo receberia custos **declarados por colaborador interno confiável**;
não calcula cotas reais, não mede memória e não transforma um custo informado
em prova de limite. Valores das fixtures seriam unidades sintéticas de bytes,
não novos defaults. Sem dependência, ambiente ou configuração externa nova.

Demonstrar nos casos e ordens exercitados apenas conservação, admissão sem
fila, transições de fechamento, retenção e liberação única do crédito lógico.
Não reivindicar linearização do registry real a partir do núcleo isolado.
Mesmo com todos os testes verdes,
B-2 permaneceria aberto. Contenção do SO, orçamento efetivo do pai e
integração são trabalhos posteriores, não funcionalidades deste lote.

## 3. Inventário e invariante propostos

Manter o contrato do desenho: `B + H + soma(W_i + P_i) <= M`.

| Parcela | Dono e conteúdo a orçar antes da alocação |
|---|---|
| `B` | Base fixa do caminho protegido, metadados limitados do ledger, capacidades de bookkeeping, gerações/snapshots publicados e aposentados, candidatos em construção, seus verificadores e auxiliares compartilhados. |
| `H` | Margem explícita, finita, reservada desde o início; não é conta para custos desconhecidos nem crédito livre para admissão. |
| `W_i` | Todo o processo worker da sessão: runtime/imports, estado persistente, libpq, AST, dados brutos, masking, codificação, instrumentação e reserva de emergência. |
| `P_i` | Custos incrementais no pai: cópias e buffers privados do snapshot da sessão, SQL, I/O, stacks de threads da sessão, buffers, frame, objetos, encoder PGWire/TLS e envio lento. A geração compartilhada fica em `B`. |
| `M` | Orçamento lógico interno do caminho protegido, não RAM física reservada nem teto do host/processo inteiro. |

Decompor `B` em base fixa + cobranças compartilhadas identificadas de geração,
candidato e auxiliares. Um guardião/launcher externo ao worker não cabe por
magia em `W_i`: se exclusivo, sua cota entra no pacote da sessão; se
compartilhado, entra em `B` com capacidade máxima própria. Inventariar cada
imagem e cada membro efetivo; redirector inesperado exige recusa, não aumento
automático de limite.

O verificador D-107 é um processo por candidato, com pipes e threads no pai:
seu custo deve integrar a cobrança de candidato em `B`, com capacidade
própria. Um teto de tempo ou semáforo existente não fornece esse custo superior
de memória. O envelope ainda não foi derivado nem imposto. Este plano não
modifica a D-107; qualquer mudança de seu contrato exigiria outro aval.

Cobrar uma geração compartilhada uma vez no pai, enquanto cada cópia no
worker integra o respectivo `W_i` e cada buffer privado integra `P_i`.
Objetos e buffers que coexistem contam simultaneamente; não deduplicar só
porque contêm bytes iguais. Não somar novamente a baseline do worker se já
incluída na cota de processo. Custos não inventariados são bloqueantes.

Reservar o custo superior da criação/compilação do candidato **antes** de
resolver/compilar/capturar/copiar seus insumos. Publicação transfere o crédito
de candidato para geração sob a mesma transição, mantendo a geração anterior
cobrada até seu descarte. Não existe intervalo com ambas presentes e uma só
cobrada. Estoque preexistente acima do orçamento recusa o modo protegido;
não admite primeiro para aferir ou corrigir a conta depois.

Descarte tem duas fases: marcar drenando sob o lock, executar descarte fora
dele e só devolver crédito numa segunda transição sob o mesmo lock, após
confirmação. Falha no descarte retém a cobrança, inclusive se o registry já
tirou a geração de sua lista. O ledger precisa representar esse pendente;
`closed=True` no registry não prova memória descartada.

Não dimensionar gerações apenas por `max_retired`: `withdraw()` não recusa
retirada, e reabilitar sem geração publicada não reserva aposentada
(`datasources.py:524–560,641–686`). Ciclos retirar → reabilitar → retirar
com sessões antigas vivas precisam ser contados. Os limites globais são
injetáveis; 32 sessões e os defaults de candidatos/aposentadas não são máximos
universais. O limite superior real, inclusive descartes em voo, continua a
derivar; insuficiência de orçamento pode recusar reabilitação/publicação,
nunca a retirada nem matar sessões admitidas para caber.

Quantidades e somas: inteiros exatos em bytes, sem `bool`, float, NaN,
infinito ou sentinela "0 = ilimitado"; validar faixas e somas antes da mutação.
Não aceitar custo/identidade vindo do cliente ou do frame do worker.
Capacidades de slots e comprimento de identificadores também são finitos.
Uma fixture que preenche a igualdade é aceita; mais um byte é recusado.

## 4. Ponto de linearização e fronteira com o registry

O registry atual já serializa as decisões de admissão, publicação, retirada e shutdown em
`DatasourceRegistry._lock`. `open_session()` cria um adapter e conecta no pai
(`runtime/datasources.py:689`); não é a lease remota do desenho. A composição
PGWire atual valida aliases, sem admitir worker. Nada disso muda neste lote.

**Contrato futuro proposto:** um único lock/coordenador protege a decisão
conjunta de geração capturada, vagas globais/por datasource, worker, todos os
créditos e barreira de shutdown. O ledger não adquire um segundo lock nem
chama de volta o registry. O núcleo isolado será exercitado com uma fachada
de teste de lock único; isso não comprova integração com o registry real.

Preparar metadados limitados antes da mutação e manter rollback das transições
parciais em falhas locais; não presumir que aritmética/atribuição Python seja
infalível sob OOM. Não executar spawn, filesystem, I/O, upstream, callbacks
de terceiros, espera de término ou descarte pesado sob o lock.

Se o rollback não puder ser concluído/comprovado, o núcleo fica terminalmente
fail-closed: recusa novas reservas e não devolve os créditos em dúvida.
Testes só injetam falhas nos pontos modelados; não comprovam segurança contra
qualquer `MemoryError` ou falha arbitrária do interpretador.

Reserva concorrente ao shutdown tem só duas conclusões: anterior à barreira,
com dono e créditos completos; ou recusada, sem reserva parcial. Uma reserva
anterior ainda não retomada precisa revalidar a barreira antes da autorização
de trabalho, conforme contrato de integração futuro. Nenhum caminho pode
reservar memória num ledger e admitir sessão noutro, com uma janela entre eles.

Publicação tem regra distinta de nova admissão: hoje `_publish()` aceita
reserva anterior à barreira enquanto `_closed` for falso
(`datasources.py:604–608`). Preservar essa conclusão na proposta: a cobrança
anterior é transferida sem crédito novo e a geração segue cobrada até o
descarte no fechamento. Não tratar essa publicação como admissão pós-barreira.

Nenhuma nova admissão espera capacidade. Recusa é imediata e sanitizada;
adquirir o lock curto não é fila de aplicação. Não enfileirar pedidos, tentar
de novo ou obter crédito emprestado de outro datasource.

## 5. Ownership e liberação

Propor tokens internos opacos, vinculados a instância, slot e época do slot,
sem segredos nem política no `repr`. Época monotônica limitada a `2^63 - 1`,
sem wrap/reinício na mesma instância; esgotar a época torna o slot indisponível.
Token antigo não corresponde à época corrente; não exige histórico ilimitado
de tokens anteriores. Token de outra instância ou estado inválido não
autoriza mutação. Estados: **reservado → vivo → drenando → liberado**, com
**retido** como estado de falha ainda pertencente ao dono, nunca crédito livre.

- Recusa antes de reservar não produz token nem altera estado.
- Falha anterior ao spawn só devolve crédito após confirmar que nenhum recurso
  foi criado e que os buffers privados foram descartados.
- Falha parcial, término normal, timeout e shutdown exigem confirmação dos
  recursos realmente criados: processo, threads, pipes, handles e saída.
  `join(timeout)`, pedido de kill, EOF ou fim de um job não bastam.
- O worker persistente ocioso continua cobrado. Resultado esperando cliente
  lento continua cobrado; nenhuma segunda consulta usa a mesma reserva
  enquanto a saída anterior estiver viva.
- Falha de reap ou descarte retém **vaga e créditos**. Repetir a liberação
  confirmada é idempotente; token inválido não devolve crédito de outro dono.
- Após retirar/aposentar geração, sessões admitidas mantêm sua geração
  (D-071). Retirada nunca mata essas sessões para recuperar orçamento.
- Gerações e candidatos também mantêm cobrança durante drenagem, descarte
  em voo ou falha; release só na segunda transição confirmada sob o lock.
- O núcleo só recebe fatos de um colaborador confiável do pai. Booleans do
  teste não são prova de término do SO, nem um ACK do filho autoriza release.

Bookkeeping terá capacidade máxima definida antes de uso, sem histórico
ilimitado de tokens liberados, aliases ou tentativas recusadas. Não alocar
relatórios, pilhas de exceção ou listas de diagnóstico sem teto sob pressão.

**Limite importante:** descartar referências não prova devolução de commit
ao SO. Arenas/caches/stacks retidos precisam caber numa reserva permanente
de capacidade máxima em `B`, não liberada a cada ciclo, ou noutro mecanismo
comprovado. Não liberar crédito de
commit real apenas porque `gc.collect()` ou um contador lógico terminou.
Esse problema continua aberto para o caminho de produto, inclusive ciclos
repetidos de admissão/remoção e gerações de tamanhos distintos.

## 6. Memória do pai: estratégia de prova, não implementação

Antes de implementar o decoder/encoder, fechar um grafo de alocações com
dimensões finitas e sobreposição temporal. Escolher e documentar representação
concreta de resultado, operações de leitura/cópia e buffers de envio; não
presumir custo de uma estrutura que ainda não existe. O subconjunto de tipos
da §6 do desenho e a recusa inteira antes de resposta parcial continuam iguais.

Para um perfil de runtime/ABI/allocator reivindicado, o custo superior precisa
incluir no mínimo:

1. snapshot, SQL, framing, cabeçalhos e buffers de I/O simultâneos;
2. contagens de colunas, linhas **e produto de células**, validadas antes de
   criar listas/objetos, compatíveis com o mínimo estrutural dos bytes restantes;
3. texto decodificado, cabeçalhos, referências, listas/tuplas, inteiros e caches;
   Unicode pode ter representação interna distinta dos bytes UTF-8;
4. frame original ainda retido, views que o mantêm vivo, cópias na validação,
   montagem PGWire, recodificação e buffers de rede/TLS coexistentes;
5. fragmentação, arenas/caches retidos entre sessões, stacks, buffers nativos,
   falhas de alocação, sanitização e cleanup com memória escassa;
6. resultados de várias sessões e gerações coexistentes, inclusive clientes
   lentos, sem reutilização prematura de `P_i`.

Cada alocação proporcional deve ter limite superior coberto e conferido antes
de ocorrer. `len(frame)`, `sys.getsizeof` isolado, fator medido médio ou maior
pico de algumas fixtures não são prova desse limite. O proxy antigo de
amplificação não é o decoder real. Amostragem é evidência complementar, não
substituto de imposição.

Se esses custos não puderem ser fechados no processo do pai atual, apresentar
**outra decisão arquitetural** antes de implementação: domínio limitado de
processo com ownership e transporte de saída também orçados. Não colocar
gateway/MCP/Admin sob Job Object, nem devolver uma estrutura ilimitada ao pai,
nem mudar silenciosamente a representação ou o contrato de resultado para
declarar B-2 resolvido. Não há alternativa aprovada neste documento.

## 7. Matriz proposta para B2-B1 — somente após autorização

Cada grupo terá casos positivos e contraprovas, com estado completo antes e
depois. Valores sintéticos pequenos, sem alocação proporcional ao crédito.
Enumerar deterministicamente as ordens das transições de admissão/fechamento
no modelo. Threads usando o mesmo lock de teste não comprovam concorrência
do registry: a futura integração terá testes de corrida próprios, com
barreiras/eventos e sem sleeps para presumir ordem.
Número final de casos será predeclarado na revisão da implementação.

| Grupo | Propriedade e recusa esperada |
|---|---|
| L1 | Validação de tipos/faixas/somas; base e margem já cobradas; igualdade aceita, excesso de um byte recusado sem mutação. |
| L2 | Disputa de duas admissões pelo último crédito/vaga, mesmo datasource e distintos: só uma confirma; limites por datasource não multiplicam `M`. |
| L3 | Falta independente de vaga global, por datasource, worker, slot ou bytes: nenhuma reserva parcial em qualquer recusa. |
| L4 | Admissão × shutdown, nos dois ordenamentos; nenhuma admissão após a barreira; publicação de candidato reservado antes dela mantém cobrança; fechamento repetido idempotente. |
| L5 | Falha em cada etapa modelada de criação/transferência de crédito; sem recurso criado libera uma vez; recurso incerto retém. |
| L6 | Worker ocioso, job concluído e cliente lento: créditos continuam; reap confirmado mas saída viva ainda impede release final. |
| L7 | Falha persistente de cleanup retém capacidade; confirmação posterior libera exatamente uma vez; pedidos duplicados não criam crédito. |
| L8 | Tokens de outra instância, época obsoleta, slot reutilizado, esgotamento da época e descarte em ordem diferente: nenhuma liberação de dono errado. |
| L9 | Candidato novo + geração antiga + sessões drenando; publicação transfere sem buraco, inclusive após barreira com reserva anterior; crédito de descarte só volta na segunda transição confirmada. |
| L10 | Crescimento de geração/base sem crédito é recusado antes da alocação modelada; ciclos retirar/reabilitar com sessões antigas não ignoram cobranças; falha de descarte retém crédito, retirada não mata sessão. |
| L11 | Capacidade máxima de bookkeeping e muitas tentativas/ciclos com objetos sintéticos, inclusive retirar/reabilitar: estado limitado, sem acumular tombstones ou aliases e sem presumir que `max_retired` cobre todos os casos. |
| L12 | Falhas locais injetadas antes/durante transições; falha do próprio rollback leva a terminal fail-closed sem crédito devolvido; não certifica todo OOM real; erro/repr/status sem segredo. |

Critério: todas as invariantes e contraprovas modeladas do núcleo passam;
liberação única refere-se ao crédito lógico, não a devolução física. Falhas e
testes não executados são registrados, sem retries automáticos até verde.
Revisão pelo Claude2 antes de fechamento; gates proporcionais e preservação
dos caminhos operacionais. Mesmo aprovado, seria **só núcleo lógico**, não
conclusão de B-2, integração ou liberação de SQL/produção.

## 8. Gates posteriores separados

| Gate pendente | Prova necessária, fora de B2-B1 |
|---|---|
| Integração do ledger | Admissão/publicação/shutdown reais sob ponto único; ordem de locks incluindo `_close_lock`, `_lock` e `lease._lock`; contrato remoto sem conexão duplicada; mesmas gerações e reservas em falhas, inclusive descarte em duas fases. |
| Contenção Windows | Perfil de imagem/runtime, criação já associada, inventário de todos os membros, cotas individuais/agregadas, saturação concorrente, OOM e recolhimento confirmados; restrições herdadas declaradas. |
| Pai real | Limites derivados para representação/codec/TLS reais, pressão e ciclos repetidos, frames válidos amplificadores/malformados, concorrência e cliente lento, sem crescimento residual não orçado. |
| Fetch/pipeline | Mesmo validator/AST/proveniência/masking; célula gigante; `max_rows + 1`; cursor/transação e `_settle` sem COMMIT; conexão por sessão e equivalência B-1. |
| Certificação | Produto e pacotes instalados nos runtimes/plataformas reivindicados, não extrapolação dos processos sintéticos. |

Se for proposta a soma de cotas individuais como contrato alternativo ao teto
agregado, isso exige aprovação explícita **separada**, argumento de cobertura
de todos os membros e comprovação própria. O registro B2-A não deu esse aval.
Não somar picos individuais de momentos diferentes como pico simultâneo.
Nem ledger correto nem limite do SO isolado resolvem a memória do pai.

O `close()` atual espera sessões/candidatos sem timeout
(`datasources.py:753–794`). Retenção fail-closed pode mantê-lo esperando;
estado/report de shutdown incompleto ainda precisa de contrato e integração
próprios. Não é corrigido nem recebe prazo neste plano. Preservar a ordem
real dos locks exige também considerar que release da lease já segura seu
lock; não adicionar aquisição bloqueante de lease sob o lock do registry
para copiar o modelo lógico.

## 9. Referências e exclusões

Contratos oficiais consultados nesta preparação; não são medição do host:

- [Microsoft — limites individuais e de job](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information): controles independentes, diferentes de uma reserva lógica.
- [Microsoft — contadores de processo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex): commit atual/pico não são working set.
- [Microsoft — Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects): associação, herança, jobs aninhados e último handle têm contratos próprios.
- [CPython — gestão de memória](https://docs.python.org/3.11/c-api/memory.html) e [sys.getsizeof](https://docs.python.org/3.11/library/sys.html#sys.getsizeof): custos do objeto isolado não fecham grafo/allocator.
- [PEP 393](https://peps.python.org/pep-0393/): representação Unicode depende do conteúdo; não igualar texto Python a bytes UTF-8.

Não alterar D-107, `db/postgres.py`, registry, leases, driver PGWire, MCP,
Admin/UI, dependências, secrets, configuração, limites ou `.venv`. Não criar
harness, worker, SQL de cliente, testes de pressão, banco/Docker ou relatório
de desempenho. Não reexecutar nem editar evidências temporárias anteriores.
Sem commit, push, deploy ou produção. Aprovar este plano não autoriza executar
B2-B1 nem seus gates posteriores; a próxima autorização deve nomear o lote.

## 10. Revisão e fechamento desta preparação

Claude2 participou da preparação e depois revisou o documento em modo
somente leitura, na sessão `f1cbda2d-81ba-4697-ad1e-272667238954`.
A revisão apontou ajustes documentais, incorporados: descarte em duas fases,
publicação pré-reservada durante shutdown, época limitada dos tokens,
rollback fail-closed, limites da prova isolada, snapshots sem dupla contagem,
custo do verificador D-107, ciclos retirar/reabilitar e retenção de memória
do alocador. Os pontos sobre o registry foram conferidos também no código
existente, sem alterá-lo.

Na rerevisão, Claude2 confirmou os dez ajustes e não apontou bloqueador
para registrar a **proposta**, sem aprovar implementação, testes ou gates.
As duas sugestões finais de redação foram incorporadas: testes do núcleo
enumeram ordens de transição, e o lock do registry serializa decisões, não
todo o trabalho de shutdown. Nenhum resultado de produto foi declarado.

Neste incremento não houve teste novo, pressão de memória, processo de probe,
SQL, PostgreSQL, Docker, pacote, browser ou instalação. A conferência contra
o freeze próprio de **344 arquivos selecionados no início** encontrou só
seis documentos existentes alterados e este plano adicionado, sem remoção;
código, testes, recursos, dependências e `.venv/pyvenv.cfg` mantiveram os
hashes. O relatório histórico e os fontes/sumário arquivados da rodada final
B2-A também mantiveram os hashes. UTF-8 estrito, whitespace e
`git diff --check` foram conferidos, sem repetir suítes para este trabalho
documental. Sem fetch, commit, emenda ou push.

**Aval solicitado ao fim da preparação (histórico):** aprovar esta proposta e autorizar somente
implementar B2-B1, núcleo lógico isolado e seus testes de estado/ordens, com
revisão pelo Claude2. Isso não inclui integração, Job Object, pressão de
memória, worker, SQL ou alteração de critérios. Naquele checkpoint, B2-B1
ainda não estava autorizado. O aval posterior e seu limite estão na §11.
B-1 fim a fim, B-2 e D-090 gate 2 seguem abertos.

## 11. Autorização e implementação posterior de B2-B1

O usuário respondeu **"sim"** em 2026-10-19 ao pedido de implementar apenas
B2-B1, controle lógico de reservas e testes determinísticos, com revisão
pelo Claude2, sem worker, SQL, pressão de memória ou commit/push. Isso
autoriza o contrato do núcleo isolado, não os demais gates/alternativas.

Implementado em `runtime/budget.py` e `tests/test_runtime_budget.py`, sem
chamador operacional. D-112 e
`PHASE-9-STAGE-8-B2-B1-VALIDATION.md`, com revisão técnica concluída sem
bloqueador no núcleo isolado. O usuário aprovou explicitamente o fechamento
do B2-B1 e a D-112 em 2026-10-20, sem autorizar integração ou os demais gates.
Os custos informados e fatos de cleanup são do modelo, não prova física.
Não há integração de lock/registry, worker ou imposição de limites do SO.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.
