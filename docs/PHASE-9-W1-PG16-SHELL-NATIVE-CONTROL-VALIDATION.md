# Orquestrador privado dos controles — validação com fakes

Data:2026-11-01, America/Sao_Paulo. Base publicada antes deste incremento:
06c4d2eb15689da10b133b61e0a288777fa7e692, com adaptador aceito em c03fd10.
Escolhas sob delegação vigente, sem atribuir aprovação individual ao usuário.
Claude2 foi o único programador, sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
sempre claude-opus-5-5/esforço medium; o assistente principal revisou, testou,
preservou dados de revisão e escreveu este registro.

## 1. Retomada e escopo

A tarefa Maskgw-Claude2-Resume-01a05804 executou às21h24m15Z/18h24m15 SãoPaulo:
LastTaskResult0 e a mensagem nesta mesma conversa confirmaram a execução.
Foi desativada e relida Disabled, sem próximo horário. Não se confunde essa
medição com a execução histórica das19h25Z. Nenhuma quota/reset foi observado;
nenhuma nova tarefa foi criada nesta retomada.

Os dois registros de continuidade foram lidos primeiro. CLI16034 foi recolhida
com resposta terminal exit0; a inspeção confirmou zero processos da sessão.
Antes de cada chamada seguinte foi conferida a ausência de escritor. Nunca
houve duas chamadas concorrentes da mesma sessão.

Entregues docs/poc/pg16_shell_native_control.py, seus testes e notas de desenho.
É uma função privada run(nonce), sem CLI, __main__ ou consumidor. Ela não foi
chamada com recursos reais. Os testes redirecionaram caminhos para tmp_path
e usaram owners/relógios/ambiente fictícios. Nonce é só identificador de
frescor/consumo, não credencial ou autoridade.

Somente Read/Edit/Write com escopos explícitos foram disponibilizados ao
programador. Não se leu explicitamente configuração ou binário de runtime.
Não houve WinDLL/API/job/processo nativo dos controles, raiz operacional,
Docker, PostgreSQL, SQL, serviço, worker ou deployment neste incremento.

## 2. Contratos conferidos

- Host e adaptador são carregados por SHA. Request, Owner e Win32Error vêm
  da mesma cópia do backend do adaptador; o loader do host não é usado.
  Limites e globals de retenção do host permanecem intactos.
- NORMAL, TERMINATE e LAST_CLOSE são os únicos casos, em ordem fixa. A
  primeira rejeição encerra tentativas; os demais ficam NOT_RUN.
- Owner é registrado antes de setup; só CLOSED permite removê-lo. Setup com
  prazo gasto ou relógio inválido impede start. READY tem contador próprio,
  preservando bytes e histórico temporal para a supervisão herdada.
- LAST_CLOSE usa snapshot estrito de OUTER e fechamento explícito de INNER.
  Após CLOSED, auditoria é capturada uma vez; resumo, critério de aceite e
  audit.json derivam do mesmo tuple e flag. Auditoria inválida, teto512
  excedido ou qualquer terminate impedem aprovação desse caso.
- Invocação durável vem antes de setup. Supervision/stdout e snapshot/audit
  aplicáveis ficam privados antes da projeção. Ambiente só pelos nomes,
  sem valores; o teste varre os bytes escritos pelos valores fictícios.
- Publicação exige todos os owners liberados. Transporte vincula tamanho/SHA
  dos brutos e resumo. Tudo, inclusive o retorno, é preparado antes da
  tentativa de rename final; não há I/O posterior, inclusive em exceção.
  Rename que realizou o efeito e depois falhou é indeterminado, não ausência
  de publicação. Diretório parcial fica consumido, sem retry ou remoção.
- Interrupção original é preservada por identidade na limpeza própria. Nova
  interrupção durante falha ordinária propaga; falhas ordinárias sem controle
  são saneadas fora do except, sem cause/context. CLOSED não vira owner vivo
  fictício quando o auxiliar falha; o não comprovado continua retido.
- Reservas contained e recorded precedem os efeitos de retenção. Reentrada
  não repete o terminate de emergência nem tentativas xb. O terminate de
  decisão do supervisor é separado e não consome a reserva de emergência.

## 3. Revisões rejeitadas e vermelho medido antes do fix

CLI16034 entregou fonte0dfcd0f4/28272bytes e testesc4c02c82/37898bytes.
70próprios/5,83s e estáticos iniciais passaram, mas a revisão independente
reproduziu trêsP2:

1. Relógio final inválido em TERMINATE era ignorado pelo motivo DEADLINE já
   esperado, aprovando caso e lote com seconds nulo.
2. Nova interrupção na limpeza de falha ordinária era descartada e resultava
   em CONTROL_INTERNAL, em vez de propagar a interrupção.
3. Falha na fronteira de _retain substituía a interrupção original e podia
   deixar owner comprovadamente CLOSED ainda registrado.

Três probes independentes com fakes concluíram19,05s e reproduziram os três
findings; saída agregada exit1. Pytest informou3passed porque os probes
coletam resultados e falham depois da restauração dos fixtures; não é aceite
do componente. O primeiro relatório tentou formatar uma falha sob o ban de
runtime e terminou INTERNALERROR/19,20s; o ban impediu a leitura.

CLI71702 escreveu apenas regressões/notas, com a fonte intacta. A execução
normal, mesmo com --tb=no, também esbarrou no ban durante a formatação da
primeira falha:70passed/5,93s,exit1, sem concluir a matriz. O revisor forneceu
apenas um pytest_runtest_makereport efêmero que retorna relatório fechado
(tipo de erro e nodeid), sem inspecionar traceback. Asserções e bloqueios do
fixture ficaram inalterados.

Assim foram medidos **8failed/72passed/6,83s,exit1**, antes de liberar o fix.
São10 casos novos (não11), incluindo dois controles que já passavam.
Testesd325b907/42602bytes e medição preservados. CLI82020 corrigiu o runner;
80próprios/5,80s passaram. Os três probes originais ficaram limpos.

Uma quarta contraprova confirmou a limitação de reentrada declarada pelo
programador: Signal em held.json fazia _held e _contain reterem novamente,
repetindo o terminate. Fonte31fd2ead/29605bytes preservada. Quatro probes/
0,88s terminaram exit1 por esse únicoP2 remanescente.

CLI91363 escreveu três regressões, preservando como prefixo exato os80 casos
anteriores. Antes do fix, fonte31fd2ead intacta: **2failed/1passed/80deselected/
1,27s,exit1**. O controle aprovado distingue o terminate do supervisor daquele
da retenção. Testes01d4abec/45808bytes preservados. CLI80293 corrigiu somente
runner/desenho; testes intactos nessa correção.

Instantâneos em docs/poc/evidence/native-control-review-20261101/, como dados
base64 e manifestos. Tamanhos/SHA são dos bytes decodificados. São baselines
rejeitadas ou regressões vermelhas, nunca controles nativos para executar.
Nenhum instantâneo anterior foi sobrescrito.

## 4. Gates finais

Windows, CPython3.11.3 da .venv. Executado só esse runtime; alvo3.14 é análise
estática. Fixture recusa WinDLL, Popen, os.system, Thread.start e leituras sob
.venv. Ferramentas fazem seus imports normais; não é promessa de ausência de
leituras implícitas do interpretador.

| Gate | Resultado |
|---|---|
| Próprios após correção da reentrada | 83passed/10,98s,exit0 |
| Quatro probes causais independentes | CLEAN,4passed/1,32s,exit0 |
| Relacionados20arquivos sobre bytes finais | 975passed/284,25s,exit0;zero falhas/skips |
| Ruff em src/tests e lint restrito do novo PoC | Aprovados |
| Formatação em src/tests e9PoCs explícitos | 353 arquivos conformes |
| Mypy alvo3.11 em src/tests | 344 arquivos,sem erros |
| Mypy alvo3.14 em src/tests | 344 arquivos,sem erros |

Após os83 testes restava uma assinatura com quebra de linha recusada pelo
formatter. Uma chamada Claude2 restrita ao teste juntou a assinatura; AST
completo é idêntico ao snapshot vermelho de83 casos. Formatação passou; a
matriz relacionada usa os bytes posteriores. Não se repetiu a própria só
por whitespace: ela integra a relacionada. Nenhum skip/xfail, supressão ou
alteração de configuração para aprovar gate.

Os20 arquivos são os19 da validação anterior do adaptador mais
tests/test_pg16_shell_native_control.py. Os relacionados continuam simulados.
Produto/src/frontend/dependências não mudaram; PostgreSQL, browsers,
wheel/sdist e suíte integral de produto não foram executados aqui. O PoC
continua fora do pacote de produto; não se declara aplicação instalada.

## 5. Bytes finais e limitações

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| docs/poc/pg16_shell_native_control.py | 30055 | b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496 |
| tests/test_pg16_shell_native_control.py | 45802 | 2aeca33d491ec477f3a6f3ea7ef8fd47e100657ddbc6dd8f40069efa0c9d128f |

Backend10c9058f, hostdfcc4ed6, adaptadoreaebedd6, preparador8d0bf39e,
sonda738ee1e3, entradaafaffad0 e exportadored491c01 reconferidos intactos.
Estado aceito de16campos e fontes/raízes consumidas continuam congelados.

Permanece o limite herdado: segunda interrupção dentro do terminate de
contenção do backend pode substituir a primeira. Nova interrupção durante
falha ordinária pode carregar essa falha no __context__ pelo encadeamento do
Python; o objeto de controle não é reescrito. Teto512 da auditoria pode ser
excedido antes dos orçamentos: rejeita como AUDIT_INVALID, sem elevar o teto.
Essas limitações não são declaradas corrigidas.

Nenhum comportamento de Job Objects foi medido. Futura partida CPython lê
implicitamente venv/config/site/DLLs/stdlib; pin do launcher e criação não são
atômicos. Não há prazo absoluto de SO nem prova de contenção de árvore
arbitrária, memória ou terceiros que duplicam handles. Morte por último
handle permanece inferência do futuro controle benigno, não certificação.

Próximo: procedimento/proposta e comando exatos revisados antes de efeitos
nativos. Esta validação não os cria nem executa. Native3s NOT_MEASURED,
entry_gate NOT_EVALUATED; Gateway indisponível e B1/B2/D090gate2/C1/SQL e
produção abertos. Gate relacionado final aprovado; parecer limitado a este
componente privado simulado, sem findings P1/P2 remanescentes nessa revisão.
