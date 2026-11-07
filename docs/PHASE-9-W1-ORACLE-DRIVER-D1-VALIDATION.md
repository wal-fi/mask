# W1 Oracle — validação D1 do driver com portas determinísticas

2026-11-06, São Paulo. Claude2 foi o único programador na sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, esforço medium.
Root revisou, mediu e escreveu este registro sob a delegação vigente.
Nenhuma aprovação individual do usuário inventada.

## Parecer e escopo

Aceito somente D1: definições de um driver sobre portas internas confiáveis
determinísticas. Nenhum main, binding físico, container, socket, thread de
trabalho, guard real, processo filho, PostgreSQL ou consulta foi executado.
Locks Python comuns coordenam o modelo. D1 não fecha W1/B1/B2/D090/C1
nem prova pin do receiver, masking, tempo de vida ou limpeza física.

| Arquivo | SHA-256 | Bytes / linhas |
|---|---|---|
| deploy/oracle9_w1_driver.py | e9d8de9bcaf3c45092baad3775b0a0b5653b430a3aece158c64e653674e3500c | 34885 / 994 |
| tests/test_oracle9_w1_driver.py | 0e9a8cc1d35f69e6ca03a14f8a910af5491df6dffadb32a432defeb445099371 | 73046 / 1929 |

## Revisão antes do código

Root reviu DRIVER-DESIGN v3 e escreveu DESIGN-REVIEW com precisões:
guard antes do loader, pins fixos, owner antes de efeitos, handoff T4,
sink com EOF por resultado, prazo agregado idle e RETAINED finito com
referência forte. Dois binds RO prospectivos preservam o núcleo puro e o
pacote instalado; nenhum mount foi criado.

CLI69762 escreveu somente o teste inicial e encerrou0; terminal recuperado,
zero escritor. Root leu todas as1547linhas/8e37628e. RED67 inicial:
6 sanidades aprovadas/61 FileNotFoundError,1,541s; estáticos limpos.
Root reproduziu sem driver dois defeitos do oráculo: GUARD/ARMED aceitavam
bool/float e o watcher já consumia STOP antes do join falho, exigindo46
leituras no fio, não45. Leitura no fio não equivale a commit da máquina.

CLI32062 corrigiu só o teste e acrescentou metadata, erro e início parcial.
RED89 preformat:22 aprovados/67 FileNotFoundError,1,323s. Ruff/format
reprovavam só uma linha102colunas; mypy limpo. CLI36682 alterou apenas a
quebra dessa linha, com AST integralmente igual ao preformat.
Teste5383286a congelado:22 aprovados/67 FileNotFoundError,1,471s;
Ruff/format/mypy3.11/3.14 limpos. Ausência não prova comportamento.

## Finding comportamental, antes da correção

CLI26490 implementou somente o módulo e encerrou0. Root recuperou o
terminal, confirmou zero escritor e leu toda a fonte d310c326:
32614bytes/947linhas.89 testes passaram1,712s e os estáticos passaram.
Essa versão foi **rejeitada e não publicada**, após sondas independentes:

- EOF observado depois do prazo retornava sink OK.
- INIT e GO observados depois do prazo permitiam23 queries fake.
- ResultSummary rows3.0 era publicado por igualdade com3.
- GuardFacts WORKER/pidTrue/dumpable1 permitia ler INIT e prosseguir.

Nenhum SQL real ou exposição operacional foi produzido; foram fakes.
Root preservou fonte/green89 rejeitados e pediu regressões antes da fonte.
CLI88584 acrescentou apenas testes e botões de fake, preservando a AST
das48 funções anteriores, que coletavam89 casos parametrizados. Root leu
o delta completo e mediu:

**RED114:92 aprovados/22 falhas AssertionError,2,458s.**

Os negativos cobrem retorno no prazo exato e depois dele: INIT, GO, STOP,
EOF e join positivo; metadata exata e perfil guard antes de leitura. Há
controles positivos e guardas que já passavam; não se diz que os25 casos
acrescentados eram todos vermelhos. Teste0e9a8cc1 congelado antes da fonte.
Ruff/format/mypy311/314 limpos.

## Correção revista

CLI91374 alterou somente a fonte e encerrou0. Root recuperou o terminal,
confirmou zero escritor e leu o delta integral:

- Cerca pós-retorno não inclusiva antes de aceitar INIT/frame, EOF ou
  resultado do join. EOF tardio nunca aprova o digest.
- Watcher recebe uma leitura cercada pelo clock, sem stop por frame vencido.
  Join tardio não comita a máquina nem publica PASS.
- Join positivo é fato do modelo: permite liberar o handle e fechar os
  endpoints, mas não transforma atraso em aprovação. Join não comprovado
  mantém o owner. D2 terá de verificar o fato fisicamente.
- Rows int exato e truncated bool exato, antes de serializar.
- Perfil GuardFacts exato de controlador conferido antes do loader/INIT.
  Nenhum parent_pid ou campo Threads inexistente foi inventado.

Root repetiu as sondas originais: EOF TIMEOUT, GO atrasado ABORTED/zero
query, metadata fracionária ABORTED e guard incompatível GUARD_FAILED,
sem ler INIT. Nenhum hack de atributo World/script encontrado na fonte.

## Gates finais

| Gate | Resultado |
|---|---|
| Testes D1 | 114 aprovados,1,959s |
| Matriz relacionada incluindo D1 | 1122 aprovados,12,188s |
| Falhas / erros / skips / xfail | 0 / 0 / 0 / 0 |
| Ruff src/tests | aprovado |
| Format src/tests | 359 arquivos conformes |
| Mypy strict src/tests, alvos3.11/3.14 | 359 arquivos, aprovado em ambos |
| Lint fonte deploy E9,F63,F7,F82 | aprovado |
| Format dos dois arquivos | 2 conformes |

Runtime Windows CPython3.11.3. O alvo3.14 foi estático, não runtime.
Fonte deploy não integra mypy src/tests; não se declara mypy integral
desse módulo. Matriz: driver, controller, w1_update/context, cycle_freshness,
runtime_snapshot, worker_protocol, worker_session (SO simulado),
datasource_destination_review e sql_validator.

Upstream22 (source20 mais núcleo/teste puro) por hash/tamanho intactos.
App124 do manifesto da candidata por hash/tamanho e conjunto de paths
inalterado. Estado16 e tentativa consumida intactos. Nenhum build de imagem
ou pacote se justifica por mudança em app inalterado; readmissão futura
continua obrigatória. Node/browsers/PG integral não foram repetidos.

## Limites e próximo incremento

Portas são código interno confiável, não sandbox contra callbacks Python
hostis. Um join/close positivo do fake é fato do modelo, não comprovação
física. O fake de sessão não implementa receiver/pin/processo. O fluxo
completo fake mantém T5_PENDING/FAIL e termina T6_UNKILLED/FAIL; SUMMARY
inclui24 e nunca imprime PASS global.

Interrupções/controle de processo e retenção física do PID1 não estão
comprovados por esses testes; D2 precisa fechar seu contrato antes de
bindings reais ou main. Não se amplia a conversão de falhas Exception
testadas para uma alegação de tratamento de todo sinal/controle nativo.

Próximo passo: leitura/desenho restritos de D2 e integração com a
WorkerSession pública, sem executar efeitos, antes dos testes correspondentes.
Continuam próprios: D3/T5, gerador das expectativas exatas de corpo,
D4/ponte/fixture/recursos/frescor, prova de vida T6 e readmissão da candidata.
Oracle Linux9.8 local permanece o destino aceito, indisponível para uso.

B1 fim a fim, B2, D090gate2, C1, pressão/concorrência, TLS, ingressos/IDEs/
MCP/Admin, patches e produção abertos. SQL PGWire continua recusada.
Nenhum serviço disponível ou novo job/quota.

Históricos, fonte rejeitada, testes e REDs preservados em
docs/poc/evidence/oracle9-w1-driver-review-20261106. CLI69762/32062/36682/
26490/88584/91374 foram recuperadas antes da chamada seguinte; único escritor.
