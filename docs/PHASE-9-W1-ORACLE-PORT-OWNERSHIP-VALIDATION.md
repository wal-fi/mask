# W1 Oracle: validação do owner puro de portas

Estado em 2026-11-12: aceito para integração **somente como modelo puro**.
Não encerra W1, a Etapa 7, os gates nativos ou a preparação de produção.
Proactor ausente; Gateway indisponível.

O adendo V4.1 em `PORT-OWNERSHIP-CONTRACT` permanece com seus bytes
revistos. Sua introdução descreve a ausência dos módulos na época da
proposta, antes desta implementação; o estado atual é o deste relatório.

## Resultado final

| Medição | Resultado |
|---|---|
| Matriz relacionada, 11 arquivos | 1.604 aprovados, 0 falhas/erros/skips |
| Casos próprios incluídos nessa matriz | 194, nos dois testes congelados |
| Tempo da matriz final | 30,578 s |
| Sondagens adicionais de prazo | 4 aprovadas; antes do suplemento, 4 divergências |
| Ruff src/tests | Aprovado |
| Lint restrito da fonte PoC | E9,F63,F7,F82 aprovado |
| Formatação da fonte e dos dois testes | Aprovada |
| Mypy strict explícito, fonte e dois testes | Aprovado para 3.11 e 3.14 |
| Mypy strict src/tests | 368 alvos aprovados para 3.11 e 3.14 |
| Integridade | 15 arquivos upstream/ponte e 124 arquivos da aplicação intactos |

Runtime medido: Windows CPython 3.11.3, pilha de QA de 64 MiB.
Python 3.14 foi alvo de análise estática; não foi executado.
O gate src/tests foi medido antes do último suplemento, que alterou somente
a fonte PoC fora desse conjunto. Depois do suplemento, foram repetidos a
matriz de 1.604 casos e todos os checks explícitos dessa fonte e seus testes.

Fonte final: `docs/poc/oracle9_w1_port_ownership.py`, 96.838 bytes,
2.657 linhas, SHA-256:
`a5d233aee8de5c2a53e72e1c8fbc858c07c72bd4947267310fa0cf5598ab2a9d`.

Testes mantidos byte a byte:

- `tests/test_oracle9_w1_port_ownership.py`: 171 casos,
  `e85f8b53a47ae060874555fcaac0eceaa819c361f9c09189fa863dfd66cc56c7`.
- `tests/test_oracle9_w1_port_ownership_review.py`: 23 casos,
  `f86f54aa1694218e331cd229c9485d8e7707613c29b54a6241089c2d2ffeda6c`.

## Autoria, leitura e aplicação

Implementação e regressões pelo Gemini Argon high/high, na mesma conversa
autorizada, durante a indisponibilidade por quota do Claude2. Claude2 não
foi retomado antes do horário informado. Root fez revisão, QA e aplicação
literal dos patches; não escreveu a lógica do owner ou dos testes congelados.

Root havia lido toda a fonte original e os oráculos antes de sua execução.
Nesta correção, leu integralmente os dois patches recebidos, 772 e 107
linhas de resposta, e comprovou aplicação com `git apply --check --recount`.
Somente Ruff mecânico foi aplicado depois, com AST idêntica antes/depois.

A autorização específica recebida cobriu os quatro arquivos de 220.935
bytes pedidos ao usuário. O pacote também continha nove blobs públicos
previamente autorizados, totalizando 665.555 bytes. Não incluiu credenciais
reais, dados de banco, configuração/runtime/ambiente, binários ou histórico.
As rejeições anteriores permaneceram registradas; não houve contorno.

As chamadas 46446 e 45316 retornaram exit 0, mas o serviço informou ERROR
por limite de saída. Isso não é quota nem SUCCESS do serviço. Os blocos
fechados recebidos foram avaliados separadamente, aplicados literalmente
e testados. A chamada intermediária 35586 terminou exit 1, sem patch.
Nenhum segundo escritor foi iniciado; terminais recuperados e zero
processos das sessões de programação conferido após o término.

## Histórico RED e correções

O RED171 original comprovou ausência do módulo: quatro sanidades aprovadas
e 167 falhas por arquivo ausente. Não era prova comportamental.
O RED23 posterior comprovou os defeitos da fonte V1: um positivo aprovado
e 22 falhas comportamentais esperadas, sem erros/skips.
Os dois conjuntos permaneceram congelados durante toda a correção.

O primeiro patch corrigiu posse de partida enfileirada, publicação única
de outcome, tempo dos eventos, exceções e controles fechados, bind de
leitura, DTOs/enums exatos, WAIT único, leitura pendente única, poll apenas
com slots originais, saturação de contadores e histórico de faults limitado.

Esse candidato passou 194 próprios e 1.604 relacionados, mas a revisão
adicional encontrou uma lacuna de expiração durante callbacks. Portanto,
esse resultado intermediário não foi aceito para publicação.

Quatro sondagens públicas com fakes determinísticos reproduziram, antes
do suplemento, resultado incorreto quando não havia poll intermediário
exatamente no prazo:

1. Handoff de escrita posterior ao prazo produzia SENT.
2. Dados posteriores ao prazo concluíam a leitura vencida com sucesso.
3. EOF posterior ao prazo também concluía essa leitura com sucesso.
4. Uma escrita síncrona que atravessava o prazo produzia SENT com tempo antigo.

Após o suplemento, as escritas preservam UNKNOWN e registram somente o
handoff físico tardio; leituras vencidas falham e os bytes continuam sob
posse do owner para uma nova leitura válida. O outcome anterior mantém
sua identidade. As quatro sondagens passaram, e a matriz integral deste
incremento foi repetida sobre a fonte final.

Na preparação do roteiro independente, a primeira tentativa do root
consultou o outcome de uma segunda leitura ainda pendente. O roteiro foi
corrigido para verificar `done()` primeiro, antes de medir o RED4; isso
foi erro do harness, não finding do produto. Nenhum teste congelado mudou.

## Evidências e limites

Evidência compacta versionável em
`docs/poc/evidence/oracle9-w1-port-tests-review-20261111/`:

- `final-validation.json`: hashes, contagens e integridade final.
- `frozen-red171.json` e `frozen-behavioral-red23.json`: medições anteriores.
- `owner-callback-deadline-probes.py`: roteiro público independente do root.
- `owner-callback-deadline-red4.json` e `owner-callback-deadline-green4.json`:
  reprodução anterior e verificação posterior, sem efeitos nativos.

Respostas brutas, propostas rejeitadas, logs, XMLs e pacotes de envio
permanecem preservados localmente, fora do conjunto de publicação.

Nenhum Docker, PostgreSQL, SQL ou operação nativa de produto foi executado.
Estado16 e tentativa consumida não foram lidos ou modificados. Não existe
prova física de quiescência, cleanup, posse de handles ou EOF neste lote.
T5 físico, B-1, B-2, D-090 gate 2, C1, D119, TLS, ingressos e produção
continuam abertos. Os limites de contadores foram verificados por código e
casos determinísticos; não se alega tráfego real de 2**63 bytes.

Próximo incremento seguro: desenho/reconciliação do adaptador concreto das
portas e de sua prova de posse/quiescência, antes de testes e fonte próprios.
Reutilizar os componentes revistos; não substituir o destino funcional por
fakes como entrega final e não executar efeitos nativos neste escopo.
