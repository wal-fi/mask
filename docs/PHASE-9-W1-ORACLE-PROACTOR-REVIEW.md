# W1 Oracle: requisitos de revisão do adaptador Proactor

2026-11-12. Parecer prévio do root sobre o mapeamento público do SDK.
Não é desenho de implementação aprovado, código ou teste nativo.
`PHASE-9-W1-ORACLE-PROACTOR-DESIGN.md` e o módulo do pump permanecem ausentes.

O pedido Gemini55124 terminou exit 3/RESOURCE_EXHAUSTED 429, sem proposta.
O serviço informou quota individual e espera de 101h10m16s, em torno de
14h07UTC de 12/11. Isso é quota observada; não repetir antes do horário
informado, mudar de conta/modelo ou tratar como o erro anterior de saída.
Claude2 continua com tentativa normal permitida somente depois de
12/11 às23hUTC informado, mesma sessão/modelo/medium. Reset não foi observado.

## Fontes examinadas sem executar

Sete arquivos do projeto foram obtidos anonimamente e comparados aos blobs
Git publicados, junto de sete fontes oficiais CPython `v3.11.3`.
Quatorze textos/499.232 bytes; HTTP200 em todos. Manifesto e hashes locais:
`docs/poc/evidence/oracle9-w1-proactor-design-review-20261112/public-package.json`.
Nenhuma configuração, conversa privada, runtime/binário ou valor operacional.

Referências primárias, fixadas na versão do runtime já medido:

- [Criação pública de subprocesso e task factory](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_events.py).
- [Transporte de subprocesso, pipes e callbacks](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_subprocess.py).
- [Criação do transporte no Windows](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_events.py).
- [Contratos públicos de transporte](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/transports.py).
- [Contratos públicos de protocolo](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/protocols.py).

A implementação interna foi lida para verificar semântica. Isso não autoriza
o futuro pump a acessar atributos privados do SDK ou a copiá-lo como outro
motor de subprocessos.

## Pontos a fechar no desenho

1. **Cleanup automático do SDK.** `BaseSubprocessTransport.close()` fecha
   pipes e pode matar um filho ainda vivo; `__del__` também chama close.
   `_make_subprocess_transport` do Windows fecha o transporte e aguarda
   sua espera interna após certas falhas. Logo, não afirmar que o SDK
   nunca fecha ou mata em falhas. Separar chamadas explícitas DISPOSE
   iniciadas pelo owner dos efeitos internos observados da biblioteca.
   Qualquer conflito com a redação de PORT-DESIGN §2.3 precisa ser
   apresentado, não resolvido por uma alteração silenciosa do contrato.

2. **Janela de partida sem observabilidade.** A criação do processo precede
   a conexão dos pipes. Uma falha antes de `connection_made` pode não expor
   transporte à superfície pública do protocolo. Falta de handle não prova
   NOT_STARTED ou recolhimento físico. Explicar a posse da tentativa,
   UNKNOWN/retido e os fatos que efetivamente permitem recuperação, sem
   fingir sucesso nem tornar todos os casos normais UNKNOWN.

3. **Ordem real e publicação única.** `_connect_pipes` agenda
   `connection_made` e os callbacks pendentes antes de concluir seu waiter.
   A proposta deve tratar essa ordem, falha após aquisição de transporte,
   exit separado de perda dos pipes e falha de startup na mesma rodada.
   Preservar a publicação única do owner, os resultados já observados e a
   retenção de fatos tardios. Não criar um segundo motor de protocolo.

4. **Loop exclusivo e limites de condução.** Preservar §2.3: nenhuma
   alteração de política/global event loop, task factory padrão e loop
   nunca exposto. Fechar `now/schedule_start/run_until` e o momento exato
   de authorize anterior ao efeito. Schedule é inerte. Reavaliar stop e
   o prazo sem callbacks externos ao período controlado, sem busy loop,
   tarefas abandonadas ou cancelamento usado como atestado de cleanup.

5. **Prazos por operação.** Não regredir os quatro casos já medidos:
   handoff tardio, data tardia, EOF tardio e write síncrono que atravessa
   o prazo. O startup concluído não limita a vida da sessão. Eventos usam
   tempo atual, o resultado vencido permanece imutável e bytes retidos
   pertencem ao owner até uma nova leitura válida ou disposição explícita.

6. **Posse e memória limitadas.** Explicar quem mantém cada Task, timer,
   transporte, protocolo e callback pendente. A liberação não pode depender
   de GC, variável global ou de supor que alguém já observou o outcome.
   Mapear as filas e o overhead do SDK sem confundi-los com o teto de bytes
   copiados pelo owner. Não inventar prova nativa pelo walker dos fakes.

7. **Diagnósticos e exceções.** O código do SDK tem caminhos de diagnóstico
   e handler de exceções. A proposta deve fechar configuração de debug e
   tratamento de erros sem registrar argv, bytes ou mensagens originais.
   Preservar a primeira identidade de controle BaseException e categorias
   públicas fechadas, sem cadeia/contexto original. Explicar falha do
   próprio handler e consumo de exceção de Task, sem cleanup implícito
   adicionado pelo pump aos handlers de erro.

8. **Disposição e encerramento.** `is_closing`, buffer zero e callback de
   conexão perdida são observações diferentes. A assinatura de close/kill
   não pode virar quitação física imediata. Fechar a ordem de encerramento
   do loop e a resposta ao término incompleto mantendo posse/capacidade
   coerentes; nenhuma liberação sobre recurso ainda incerto.

9. **Seam mínimo de teste.** Definir a menor superfície tipada específica
   para testar esses fatos com SDK falso, sem criar loop, thread, processo,
   socket ou DLL reais. Exigir caminhos positivos completos e adversariais,
   inclusive falha antes/depois de aquisição, dados/exit/EOF em ordens
   diferentes, erro no transporte, controle e filas saturadas. Isso não
   substitui o adaptador funcional nem é prova nativa. Não alterar owner,
   testes congelados, DTOs/enums ou APIs aceitas para facilitar o binding.

## Ordem da continuação e limites de evidência

Primeiro, o programador devolve somente o desenho concreto e a matriz
determinística. Root lê toda proposta e deltas antes de adotar. Depois vêm
oráculos novos revistos e RED medido; somente então fonte própria. O módulo
Proactor não deve aparecer antes dessa sequência. Não executar o SDK
baixado, importar módulos para experimentar efeitos ou inventar valores
operacionais neste lote.

As futuras provas nativas precisam medir a ordem dos callbacks, efeito de
buffer zero, fechamento/recolhimento e posse por identidade na versão real,
com o plano e o destino explicitamente admitidos. Não são satisfeitas por
bools True, fake OS, exit de um wrapper ou mera ausência de mensagem.

Owner `a5d233ae`, testes `e85f8b53/f86f54aa`, ponte/host/driver/core,
aplicação124, estado16 e tentativa consumida permanecem fixos. Os 1.604
testes e quatro probes do incremento anterior são históricos, não novos
testes deste documento. T5 físico/B-1/B-2/D-090 gate2/C1/D119/TLS/ingressos/
produção continuam abertos; Gateway indisponível.
