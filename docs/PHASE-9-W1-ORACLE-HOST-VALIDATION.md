# W1 Oracle: reator puro do host — validação

2026-11-10. Implementação privada de modelo do protocolo, sob delegação;
nenhuma aprovação individual do usuário inventada. Claude2 programou sozinho
na sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, effort medium.
Root revisou e executou QA. Publicação só após os resultados abaixo.

## Resultado e escopo

Novo docs/poc/oracle9_w1_host_reactor.py: e86f8e325410a26efeb47de1c4e349e9099673de612c028eb30e01ceea5d91ae,
38610bytes/1104linhas. Teste tests/test_oracle9_w1_host_reactor.py:
f177102a1ea55e9c6a32d1fcd863f18a2c04800588bddeeab8ee0eb192816613,
77736bytes/2144linhas. Definições puras, não pacote/entrypoint/CLI.

Core carregado confiável, INIT único, espelho ControlMachine real, DTOs
imutáveis e entradas carriers, gramática fechada/512bytes/56linhas, pendência
única/recibos, prazos originais, órfãos retidos e conclusãoT6 conservadora.
pack_control confere campos do decoder, sem criar espelho. TRACE sintético
54linhas/50controles/58saídasSendAct; ARMED25 informa51, não existe frame51.
T6 só vira COMPLETE_CANDIDATE após kill tempestivo alegado, EOF/reap e
ZERO_BACKENDS25 exato. Done não é limpeza física nem PASS global/nativo.

## Revisão e sequência real

- CLI77325/56251/97378/76400/60662 encerradas0 e recuperadas antes de nova
  chamada. Guardas de zero escritor. Sem outro programador ou Gemini novo.
- Root leu todo testeV1 (1721linhas), deltaV2, toda fonteV1, regressões
  aditivas113linhas e todo delta final. Reviews HOST-TEST-REVIEW e
  HOST-SOURCE-REVIEW; precisões complementam HOST-DESIGN aed85ad4.
- V1test228:3sanidades PASS/225ausênciaFAIL. Ruff4diagnósticos e7trechos de
  formato; mypy1teste nos dois alvos limpo. Preservado, não renomeado verde.
- TesteV2 c595c426/73515bytes: RED335 com3sanidades PASS/332ausênciaFAIL,
  64,156s. Ruff/format/mypy limpos. Ausência não prova comportamento.
- FonteV1 f7de78b2:335PASS em5,453s, mas revisão independente encontrou três
  defeitos. Formato ainda falhava em uma assinatura. Candidata não publicada.
- Inteiro10**400 escapava OverflowError e não marcava recusa; Line repr
  mostrava pacote/strings sintéticas; falha de efeito conservava NOT_RUN/PASS.
- TesteR1 f177102a mantém prefixo73515bytes idêntico. RED comportamental366:
  336PASS/30FAIL/0erros/skips em11,672s (14Overflow,1repr,15veredictos).
  Contraprova segundoExited comZERO pendente já passava. Teste congelado
  antes de mudar fonte; sem skip/xfail/ignore/cast/supressão ou SDK fake.
- Fix mínimo: não representável vira TIME/POLICY fechada; reprLine redigido;
  efeitos falhos/UNKNOWN/tardios marcam só seu casoFAIL antes de DRAINING,
  substituindo PASS anterior em restore/zero. Assinatura de formato ajustada.

## Gates finais medidos

| Gate | Resultado |
|---|---|
| pytest relacionado (8arquivos) |1215PASS,0falhas/erros/skips,21,578s runner;19,516s JUnit|
| próprios dentro dessa execução |366PASS,0falhas/erros/skips|
| sondas independentes API pública |18passaram; numérico/repr/efeitos/segundoExit/pósDone|
| Ruff src/tests + lint restrito PoC |limpos|
| formato src/tests +5fontes privadas/deploy |370conformes|
| mypy strict src/tests alvo3.11 |365arquivos limpos|
| mypy strict src/tests alvo3.14 |365arquivos limpos|
| integridade |11upstream e124insumos públicos iguais por SHA/tamanho|

Runtime só Windows CPython3.11.3, pilha64MiB no runner de testes. Mypy3.14 é
análise estática, não execução3.14; PoC está fora do mypy. Nenhum Linux
medido neste lote. SDK/app/pyproject/dependências/recursos UI imutáveis; sem
necessidade de repetir Node/PG/wheel para essa adição privada não embarcada.
A evidência guarda comandos, códigos, JUnit/logs LF de exibição e bytes brutos
comprimidos em JSON; histórico de falhas preservado. Não executar snapshots
.txt como programa. Nenhum segredo real foi lido/usado nas sondas.

## Limites e próximo passo

Modelos/ports relatados não atestam kernel, identidade/frescor, exit do
container, kill próprio, ausência de backends ou limpeza. O caminho de T6
sem orçamento é apenas FAIL sem kill; nenhum flag/Done autoriza liberação.
Bridge futura deve respeitar serialização de timestamps do contrato e
reter owner/pendências antes dos efeitos. Pins de origem são do chamador;
ModuleType/shape não autenticam arquivo. Perfil/margens nativas continuam
NOT_PREPARED. A projeção imutável mínima de expected foi aceita sob delegação.

Próximo incremento seguro: somente desenho da ponte duplex e suas portas
concretas, reusando os componentes revistos, antes de novos testes/fonte ou
efeitos. Mesmo únicoClaude2/sessão/modelo/medium, guardaGit/zeroescritor e
terminal recuperado; se ativo, monitorar só. Source/teste deste lote e todos
upstream/app124/estado16/attempt consumido ficam fixos. Não ler runtime,
config privada, binários ou estado operacional para preparar esse desenho.

Sem Docker/PG/SQL/nativo/guard/socket/thread/process/signal reais, root/nonce/
comando/deploy neste lote (processos comuns CLI/QA, locks de modelo e leituras
de fontes públicas são a infraestrutura de revisão). Não houve quota nova,
retomada agendada nova ou mudança de conta/modelo. Gate nativo/T5 físico/
B1/B2/D090gate2/C1/ingressos/TLS/IDE/produção continuam abertos. Gateway
indisponível; SQL PGWire permanece recusada. Um laboratório verde ainda não
seria release de produto. Destino aceito segue OracleLinux9.8 local futuro.
