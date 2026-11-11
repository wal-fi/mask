# W1 Oracle: ponte duplex pura — validação

2026-11-11. Lote de implementação sob delegação. Claude2 escreveu toda a
fonte na sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5,
effort medium. Root revisou e executou QA. Não é entrega nativa ou release.

## Resultado

- Fonte docs/poc/oracle9_w1_duplex_bridge.py:
  5a09be1c9af3222f918973b426ae349e9f614fb4de191e7807ec8193775a98cd,
  35821bytes/974linhas.
- Teste tests/test_oracle9_w1_duplex_bridge.py:
  97c26fbfd2823e288a450fdde7ca3d7919ef7a5ec4843021bc3cb98bf585f671,
  76446bytes/1935linhas, idêntico ao RED195 congelado no commit local43f2a48.
- API síncrona com portas injetadas, cinco slots originais antes dos
  efeitos, colheita única e retenção de operações/erros incertos. Status
  somente em cache; DTOs com repr redigido; prazo global antes de todo
  feed/begin; fila FIFO limitada e recibo antes de Line/Exited. Reator
  real permanece o único decisor de protocolo, sequência e cercaT6.
- Arquivo privado de definições, fora do pacote instalado. Nenhum novo
  entrypoint, listener, CLI, dependência, recurso UI ou chamada operacional.

## Revisão e histórico preservado

Root leu toda V1 de931linhas e todos os deltas subsequentes. CLI20996,
2071,67370 e71321 encerraram0/success; terminais recuperados e zero
escritores conferido antes de cada nova chamada/revisão. Nenhum comando
do programador, segundo escritor, quota ou fallback novo neste lote.

A V1 passou195testes, mas foi rejeitada por4sondas independentes antes do
fix: status chamava reator; erro original de outcome não ficava no cache;
lookup repetido escapava RuntimeError cru; dreno começava depois do EOF
já observado e estendia0.984375s. V2 corrigiu as4sondas. Outra sonda RED
isolou a adoção tardia do processo: outcome/op retinham o recurso, mas
status.process era None após overall. V3 corrigiu isso e fechou tipagem.
Sexta sonda RED isolou a checagem inicial: um relógio finito extremo fazia
o orçamento arredondar para o início, mas1spawn ainda era iniciado antes
de recusar. V4 observa/checka o relógio antes desse primeiro efeito.

Nenhum teste congelado foi alterado ou enfraquecido. Não se afirmou perda
de recurso onde o slot original ainda o retinha. Valores extremos são
limites do contrato, não alegação de relógio nativo medido. Snapshots,
diagnósticos e REDs continuam em DUPLEX-SOURCE-REVIEW e em
docs/poc/evidence/oracle9-w1-duplex-source-review-20261111/.

## Gates finais medidos

| Gate | Resultado |
|---|---|
| Pytest relacionado,9arquivos |1410PASS,0falhas/erros/skips;37,547s|
| Próprios dentro dessa rodada |195PASS|
| Sondas independentes de API pública |6PASS|
| Ruff src/tests e lint restrito da PoC |Limpos|
| Format src/tests e6fontes explícitas |372arquivos conformes|
| Mypy strict alvo3.11 |367arquivos limpos|
| Mypy strict alvo3.14 |367arquivos limpos|
| Integridade |13protegidos e app124 intactos por SHA/tamanho|

Runtime só Windows CPython3.11.3. A pilha64MiB pertence apenas ao runner
de QA; mypy3.14 é estático, não runtime3.14. A rodada1410inclui os1215
anteriores e os195novos. JUnit foi conferido por testcase/classe; não se
deduziu contagem por barras de progresso. Saídas/XML originais preservados
comprimidos antes de normalizar a apresentação LF. O teste não sofreu
formatação ou edição de root, e os bytes finais serão conferidos no Git.

O check do índice apontou1linha vazia extra no EOF de cada um dos3scripts
de sondas guardados como dados.txt. A apresentação foi normalizada; AST
idêntica e bytes originais comprimidos em probe-presentation-review.json.
Nenhuma fonte/oráculo funcional mudou; gates não foram repetidos por isso.

## Limites e próximo incremento

Portas falsas comprovam lógica, não preempção ou latência do SO, conexão
real, identidade de container, efeito próprio de kill, EOF físico/reap,
ausência de backends ou quiescência das ações. Done/COMPLETE_CANDIDATE não
é release, cleanup nem aprovação de produção. O chamador ainda deve
autenticar/pinar o reator; ModuleType/shape não autenticam origem.

Próximo lote seguro: reconciliar o desenho público da readmissão com a
ponte e seus pins atuais e fechar o contrato concreto das portas/posse/
quiescência antes de qualquer ligação ao SO real. Reusar ledger/portas
revistos, sem outro motor de protocolo ou framework genérico de SO.
Mesmo único Claude2/sessão/modelo/medium; Git atual/zero escritor e
terminal recuperado antes de nova chamada. Novos testes/RED antes da
futura fonte; root revisa antes de executar. Não reutilizar guardas antigas.

SDK/main/driver/puro/EXPECT/host/testes anteriores/app124/estado16/attempt
consumido permanecem fixos. Nenhum Docker/PG/SQL/socket/thread/processo/
eventloop/guard/sinal nativo do produto, runtime/config/privado/binário,
raiz operacional, nonce, estado ou deployment foi acessado neste lote.
Processos normais CLI/QA e leituras públicas são infraestrutura de revisão.

T5físico/B1/B2/D090gate2/C1/TLS/ingressos/IDE/produção continuam abertos;
Gateway indisponível e SQL PGWire recusada. OracleLinux9.8 local continua
destino futuro identificado; sua disponibilidade atual não foi presumida.
Nenhum job novo foi necessário: as4chamadas retornaram sem quota. O job
anterior já entregue não tem próximo disparo conhecido.
